"""Pont entre le CRM et le back-end de generation/envoi existant (src/).

Genere un document pour un patient a partir d'un modele, enregistre le fichier
dans output/, cree l'entree `documents`, et permet l'envoi par email (Mailjet).
Reutilise src.doc_filler, src.pdf_to_jpg et src.mailer sans les modifier.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import traceback
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from src.config import Config
from src.doc_filler import WordSession, format_montant
from src.mailer import MailjetClient, MailjetError, log_mail
from src.pdf_to_jpg import pdf_first_page_to_jpg

from . import repo, templates
from .db import app_dir
from .repo import Document, Facture, Patient, Prestataire
from .templates import Template


def output_dir() -> Path:
    d = app_dir() / "output"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slug(value: str) -> str:
    return repo.slugify(value)


def patient_dir(patient: Patient) -> Path:
    """Dossier d'archive d'un patient : output/<nom>_<prenom>_<naissance>/.

    Regroupe tous les documents generes d'une fiche dans un meme dossier. La date
    de naissance distingue les homonymes ; absente, elle est simplement omise.
    """
    parts = [_slug(patient.nom), _slug(patient.prenom)]
    if patient.date_naissance:
        parts.append(_slug(patient.date_naissance))
    name = "_".join(p for p in parts if p) or f"patient_{patient.id}"
    d = output_dir() / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def build_filename(
    patient: Patient,
    doc_type: str,
    acte_date: date,
    ext: str,
    doc_id: Optional[int] = None,
) -> str:
    ext = ext.lstrip(".").lower()
    base = (
        f"{_slug(patient.nom)}_{_slug(patient.prenom)}_"
        f"{_slug(doc_type)}_{acte_date.strftime('%Y-%m-%d')}"
    )
    # L'id du document garantit l'unicite : plusieurs notes du meme type/date pour
    # un meme patient ne s'ecrasent plus (chaque version = une ligne `documents`).
    if doc_id is not None:
        base = f"{base}_{doc_id}"
    return f"{base}.{ext}"


# --- Factures fournisseurs (v6) : import/archivage, sans Word ni Mailjet ------

def prestataire_dir(prestataire: Prestataire) -> Path:
    """Dossier d'archive d'un prestataire : output/prestataires/<nom>_<prenom>/.

    Sous-dossier dedie pour ne jamais collisionner avec les notes patients.
    """
    parts = [_slug(prestataire.nom), _slug(prestataire.prenom or "")]
    name = "_".join(p for p in parts if p) or f"prestataire_{prestataire.id}"
    d = output_dir() / "prestataires" / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def import_facture(
    conn: sqlite3.Connection,
    prestataire: Prestataire,
    src_path,
    *,
    montant: Optional[float] = None,
    libelle: Optional[str] = None,
) -> Facture:
    """Archive le fichier uploade (PDF/image) et cree la ligne `factures`.

    Pas de generation Word, pas d'envoi Mailjet : archivage seul. Le nom est horodate
    pour garantir l'unicite (entre imports et vis-a-vis des patients).
    """
    src = Path(src_path)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    ext = src.suffix.lower()
    dest = prestataire_dir(prestataire) / f"facture_{stamp}{ext}"
    shutil.copy2(src, dest)
    facture = Facture(
        id=None,
        prestataire_id=prestataire.id,  # type: ignore[arg-type]
        fichier=str(dest),
        nom_original=src.name,
        montant=montant,
        libelle=libelle,
    )
    return repo.create_facture(conn, facture)


# Balises remplies automatiquement depuis la fiche patient (non demandees a l'ecran).
AUTO_PATIENT_TAGS = {"NOM", "PRENOM", "EMAIL", "TELEPHONE", "ADRESSE", "DATE_NAISSANCE"}


def _fmt_naissance(iso: Optional[str]) -> str:
    if not iso:
        return ""
    try:
        return date.fromisoformat(iso).strftime("%d/%m/%Y")
    except ValueError:
        return iso


def _patient_replacements(patient: Patient) -> dict[str, str]:
    return {
        "<NOM>": patient.nom,
        "<PRENOM>": patient.prenom,
        "<EMAIL>": patient.email or "",
        "<TELEPHONE>": patient.telephone or "",
        "<ADRESSE>": patient.adresse or "",
        "<DATE_NAISSANCE>": _fmt_naissance(patient.date_naissance),
        "<DATE_NAISSANCE_ISO>": patient.date_naissance or "",
    }


def _format_variable(tag: str, raw: str) -> dict[str, str]:
    """Formate une variable saisie selon son nom (date / montant / texte)."""
    t = tag.upper()
    raw = (raw or "").strip()
    out: dict[str, str] = {}
    if "DATE" in t:  # valeur ISO issue du datepicker -> jj/mm/aaaa (+ derive _ISO)
        try:
            d = date.fromisoformat(raw)
            out[f"<{t}>"] = d.strftime("%d/%m/%Y")
            out[f"<{t}_ISO>"] = d.isoformat()
        except ValueError:
            out[f"<{t}>"] = raw
    elif "MONTANT" in t or "PRIX" in t or "TARIF" in t:
        try:
            v = float(raw.replace(",", "."))
            out[f"<{t}>"] = format_montant(v)
            out[f"<{t}_BRUT>"] = str(v)
        except ValueError:
            out[f"<{t}>"] = raw
    else:
        out[f"<{t}>"] = raw
    return out


_MONTANT_KEYS = ("MONTANT", "PRIX", "TARIF")


def parse_montant_str(raw: Optional[str]) -> Optional[float]:
    """Parse une chaine montant (virgule ou point) en float, sinon None."""
    if not raw:
        return None
    try:
        return float(str(raw).replace(",", "."))
    except ValueError:
        return None


def _parse_montant(variables: dict[str, str]) -> Optional[float]:
    for key in _MONTANT_KEYS:
        montant = parse_montant_str(variables.get(key))
        if montant is not None:
            return montant
    return None


def _acte_date_from_variables(variables: dict[str, str]) -> date:
    """Date de l'acte : balise DATE si fournie, sinon aujourd'hui (nom de fichier)."""
    if variables.get("DATE"):
        try:
            return date.fromisoformat(variables["DATE"])
        except ValueError:
            pass
    return date.today()


def _draft_fields_from_variables(
    variables: dict[str, str]
) -> tuple[date, Optional[float], Optional[str]]:
    """Champs derives des saisies, partages par save_draft et update_draft."""
    return (
        _acte_date_from_variables(variables),
        _parse_montant(variables),
        (variables.get("ACTE") or None),
    )


def save_draft(
    conn: sqlite3.Connection,
    patient: Patient,
    template: Template,
    *,
    variables: Optional[dict[str, str]] = None,
    output_format: str = "jpg",
    doc_type: Optional[str] = None,
) -> Document:
    """Enregistre un brouillon : memorise les saisies SANS generer le fichier.

    Traitement rapide (aucun appel Word). Le fichier sera produit plus tard par
    `render_document`, depuis la fiche patient ou un job par lot.
    """
    variables = variables or {}
    doc_type = doc_type or template.name
    ext = output_format.lstrip(".").lower()
    if ext not in ("jpg", "pdf"):
        raise ValueError("output_format doit etre 'jpg' ou 'pdf'.")

    acte_date, montant, acte = _draft_fields_from_variables(variables)
    doc = Document(
        id=None,
        patient_id=patient.id,  # type: ignore[arg-type]
        type=doc_type,
        template=template.name,
        acte=acte,
        montant=montant,
        acte_date=acte_date.isoformat(),
        file_path=None,
        output_format=ext,
        statut="brouillon",
        date_generation=None,
        email=patient.email,
        variables=json.dumps(variables, ensure_ascii=False) if variables else None,
    )
    return repo.create_document(conn, doc)


def update_draft(
    conn: sqlite3.Connection,
    document: Document,
    *,
    variables: dict[str, str],
    output_format: str = "jpg",
) -> Document:
    """Met à jour les saisies d'un brouillon existant (reste un brouillon)."""
    ext = output_format.lstrip(".").lower()
    if ext not in ("jpg", "pdf"):
        raise ValueError("output_format doit etre 'jpg' ou 'pdf'.")
    acte_date, montant, acte = _draft_fields_from_variables(variables)
    document.acte = acte
    document.montant = montant
    document.acte_date = acte_date.isoformat()
    document.output_format = ext
    document.statut = "brouillon"
    document.variables = json.dumps(variables, ensure_ascii=False) if variables else None
    repo.update_document(conn, document)
    return document


def render_document(conn: sqlite3.Connection, document: Document) -> Document:
    """Produit le fichier d'un brouillon existant et met a jour son statut.

    Reconstruit les remplacements depuis `document.variables` + la fiche patient,
    lance Word (PDF/JPG). En cas d'echec, passe le document en statut 'erreur'.
    """
    patient = repo.get_patient(conn, document.patient_id)
    if patient is None:
        raise ValueError("Patient introuvable pour ce document.")

    template = templates.get_template(document.template or document.type)
    if template is None:
        raise ValueError(f"Modele introuvable : {document.template or document.type}")

    ext = (document.output_format or "jpg").lstrip(".").lower()
    if ext not in ("jpg", "pdf"):
        ext = "jpg"
    try:
        acte_date = date.fromisoformat(document.acte_date) if document.acte_date else date.today()
    except ValueError:
        acte_date = date.today()

    variables: dict[str, str] = {}
    if document.variables:
        try:
            variables = json.loads(document.variables)
        except (ValueError, TypeError):
            variables = {}

    # Categorie (attribut du modele) : range le fichier dans un sous-dossier dedie
    # et fige le libelle sur le document (snapshot). Sans categorie => racine du
    # dossier patient (comportement historique). Le dossier utilise le slug (sur),
    # la colonne garde le libelle brut (lisible).
    categorie = repo.get_template_category(conn, template.name)
    document.categorie = categorie
    base_dir = patient_dir(patient)
    if categorie:
        base_dir = base_dir / _slug(categorie)
        base_dir.mkdir(parents=True, exist_ok=True)
    out_path = base_dir / build_filename(
        patient, document.type, acte_date, ext, doc_id=document.id
    )
    repl = _patient_replacements(patient)
    for tag, raw in variables.items():
        if tag.upper() in AUTO_PATIENT_TAGS:
            continue  # ne pas ecraser les champs patient
        repl.update(_format_variable(tag, raw))

    try:
        with WordSession() as word:
            if ext == "pdf":
                word.fill_and_export_pdf(template.path, repl, out_path)
            else:
                with tempfile.TemporaryDirectory() as tmp:
                    pdf_path = Path(tmp) / (out_path.stem + ".pdf")
                    word.fill_and_export_pdf(template.path, repl, pdf_path)
                    pdf_first_page_to_jpg(pdf_path, out_path)
    except Exception as exc:  # noqa: BLE001
        document.statut = "erreur"
        document.message_erreur = f"{exc}\n{traceback.format_exc()}"
        repo.update_document(conn, document)
        raise

    document.file_path = str(out_path)
    document.output_format = ext
    document.statut = "en_attente_envoi" if patient.email else "genere"
    document.date_generation = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    document.message_erreur = None
    repo.update_document(conn, document)
    return document


def move_documents_to_category(
    conn: sqlite3.Connection,
    documents: list[Document],
    nouvelle_categorie: str,
) -> int:
    """Deplace best-effort les fichiers de documents reclasses vers le sous-dossier
    de leur nouvelle categorie, et met a jour `file_path`/`categorie` en base.

    Appelee APRES commit de `repo.rename_category(..., reclasser_documents=True)`
    (qui a deja repercute `documents.categorie` en base et renvoie les documents
    concernes avec leur ancien `file_path`). Les erreurs d'I/O sont non bloquantes
    et journalisees (audit) : un fichier verrouille/absent n'interrompt pas le lot.
    Renvoie le nombre de fichiers effectivement deplaces.
    """
    slug = _slug(nouvelle_categorie)
    moved = 0
    for d in documents:
        if not d.file_path:
            continue
        src = Path(d.file_path)
        if not src.exists():
            continue
        patient = repo.get_patient(conn, d.patient_id)
        if patient is None:
            continue
        try:
            dest_dir = patient_dir(patient) / slug
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / src.name
            if dest == src:
                continue
            shutil.move(str(src), str(dest))
            d.file_path = str(dest)
            d.categorie = nouvelle_categorie
            repo.update_document(conn, d)
            moved += 1
        except OSError as exc:
            repo.log_audit(
                conn, "categorie_fichier_non_deplace",
                f"#{d.id} -> {slug} : {exc}",
            )
            continue
    return moved


def send_document(
    conn: sqlite3.Connection,
    document: Document,
    config: Config,
    template_id: int | None = None,
) -> None:
    """Envoie un document genere par email via Mailjet et met a jour son statut.

    `template_id` : ID du template Mailjet choisi (sinon celui de config.ini).
    """
    if not document.email:
        raise ValueError("Aucune adresse email pour ce document.")
    path = Path(document.file_path or "")
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {path}")

    patient = repo.get_patient(conn, document.patient_id)
    acte_date = ""
    if document.acte_date:
        try:
            acte_date = date.fromisoformat(document.acte_date).strftime("%d/%m/%Y")
        except ValueError:
            acte_date = document.acte_date
    variables = {
        "prenom": patient.prenom if patient else "",
        "nom": patient.nom if patient else "",
        "montant": format_montant(document.montant) if document.montant else "",
        "acte": document.acte or "",
        "date": acte_date,
        "type_document": document.type.replace("_", " "),
    }

    mailjet = MailjetClient(config.mailjet, config.mail)
    try:
        result = mailjet.send(
            document.email, path, custom_id=path.name, variables=variables,
            template_id=template_id,
        )
        document.statut = "envoye"
        document.date_envoi = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        document.mailjet_message_id = result.message_id
        document.mailjet_status = "sent"
        document.date_refresh_status = document.date_envoi
        document.message_erreur = None
    except MailjetError as exc:
        document.statut = "erreur_envoi"
        document.message_erreur = str(exc)
        log_mail(
            "DOCUMENT_SEND_ERROR",
            document_id=document.id, to=document.email, file=path.name, error=str(exc),
        )
        repo.update_document(conn, document)
        raise
    except Exception as exc:  # noqa: BLE001
        document.statut = "erreur_envoi"
        document.message_erreur = f"{exc}\n{traceback.format_exc()}"
        log_mail(
            "DOCUMENT_SEND_ERROR",
            document_id=document.id, to=document.email, file=path.name,
            error=str(exc), traceback=traceback.format_exc(),
        )
        repo.update_document(conn, document)
        raise
    log_mail(
        "DOCUMENT_SENT",
        document_id=document.id, to=document.email, file=path.name,
        message_id=document.mailjet_message_id,
    )
    repo.update_document(conn, document)


def _event_state(ev: dict) -> str:
    return str(ev.get("State") or ev.get("EventType") or "").lower()


def _event_time(ev: dict) -> Optional[str]:
    """Convertit `EventAt` (timestamp Unix) en 'AAAA-MM-JJ HH:MM:SS' local."""
    raw = ev.get("EventAt") or ev.get("ArrivedAt")
    if not raw:
        return None
    try:
        return datetime.fromtimestamp(int(raw)).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError, OverflowError, TypeError):
        return None


def _earliest_event(events: list[dict], state: str) -> Optional[str]:
    """Horodatage du premier evenement d'un type donne (ex. 'opened', 'clicked')."""
    times = [t for ev in events if _event_state(ev) == state
             for t in [_event_time(ev)] if t]
    return min(times) if times else None


def refresh_mail_status(
    conn: sqlite3.Connection, document: Document, config: Config
) -> str:
    """Interroge Mailjet pour le suivi de livraison d'un document envoyé.

    Met à jour `mailjet_status`, `date_refresh_status`, et — via la chronologie
    `messagehistory` — les horodatages de 1re ouverture / 1er clic. Renvoie le statut.
    """
    if not document.mailjet_message_id:
        raise ValueError("Aucun identifiant Mailjet pour ce document.")
    mailjet = MailjetClient(config.mailjet, config.mail)
    status = mailjet.fetch_message_status(document.mailjet_message_id)
    document.mailjet_status = status
    document.date_refresh_status = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Chronologie detaillee (best-effort : ne pas faire echouer le refresh du statut).
    try:
        events = mailjet.fetch_message_history(document.mailjet_message_id)
        opened = _earliest_event(events, "opened")
        clicked = _earliest_event(events, "clicked")
        if opened:
            document.mailjet_opened_at = opened
        if clicked:
            document.mailjet_clicked_at = clicked
    except MailjetError:
        pass
    repo.update_document(conn, document)
    return status
