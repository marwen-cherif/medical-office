"""Pont entre le CRM et le back-end de generation/envoi existant (src/).

Genere un document pour un patient a partir d'un modele, enregistre le fichier
dans output/, cree l'entree `documents`, et permet l'envoi par email (Mailjet).
Reutilise src.doc_filler, src.pdf_to_jpg et src.mailer sans les modifier.
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import tempfile
import traceback
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from src import odontogram_render
from src.config import Config
from src.doc_filler import WordSession, classify_placeholders, format_montant
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

# Balises de note DERIVEES des dents, calculees a la generation : jamais saisies a
# l'ecran (comme les balises patient). `<DENTS>` reste, lui, saisissable (via le bloc
# de selection FDI dans le dialogue de generation). Cf. schema-dentaire-notes.
DERIVED_NOTE_TAGS = {"NB_DENTS", "ODONTOGRAMME"}


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


# --- Note multi-lignes (facturation-multi-lignes) -----------------------------
# Contrat de balises standard « a la Mailjet » consomme par les modeles « note
# multi-lignes ». Un modele est multi-lignes des qu'il porte >= 1 balise de ligne
# <L_*> (cf. src.doc_filler.classify_placeholders). Aucune configuration de
# colonnes par modele : le contrat est fixe et documente (CLAUDE.md).

# Cle reservee de documents.variables : liste des lignes BRUTES retenues. Les
# totaux et formats sont RECALCULES au rendu, jamais stockes (design D7).
LIGNES_KEY = "__lignes__"

# Balises de ligne (repetees par ligne) et balises document calculees (totaux).
LINE_TAGS = ("L_DATE", "L_ACTE", "L_DENTS", "L_NOTE", "L_MONTANT", "L_REGLE", "L_RESTE")
TOTAL_TAGS = ("TOTAL_DU", "TOTAL_REGLE", "RESTE_A_PAYER", "NB_ACTES", "TOTAL")


def _ligne_num(value) -> float:
    """Montant d'une ligne en float ; vide/non numerique -> 0 (design D5)."""
    if value is None or value == "":
        return 0.0
    try:
        return float(str(value).replace(",", "."))
    except (ValueError, TypeError):
        return 0.0


def prestation_to_ligne(pres: "repo.Prestation") -> dict:
    """Projette un acte (repo.Prestation) en ligne de contexte BRUTE (design D4)."""
    return {
        "source": "acte",
        "prestation_id": pres.id,
        "date": pres.date_acte or "",
        "acte": pres.libelle or "",
        "dents": pres.dents or "",
        "note": pres.note or "",
        "montant": float(pres.montant or 0),
        "regle": float(pres.montant_regle or 0),
    }


def total_du_lignes(lignes: list[dict]) -> float:
    """Total du NUMERIQUE (pour document.montant : affichage/email, jamais une creance, D6)."""
    return sum(_ligne_num(l.get("montant")) for l in lignes)


def totaux_num(lignes: list[dict]) -> tuple[float, float, float, int]:
    """(total_du, total_regle, reste, nb_lignes) NUMERIQUES — pour l'affichage UI
    (recap en direct), la mise en forme restant a la charge de l'appelant."""
    du = total_du_lignes(lignes)
    regle = sum(_ligne_num(l.get("regle")) for l in lignes)
    return du, regle, du - regle, len(lignes)


def compute_totaux(lignes: list[dict]) -> dict[str, str]:
    """Totaux FORMATES (style FR) calcules sur les lignes retenues (design D5).

    `TOTAL_DU` = somme des montants ; `TOTAL_REGLE` = somme des regles ;
    `RESTE_A_PAYER` = du - regle ; `NB_ACTES` = nb de lignes (entier) ;
    `TOTAL` = alias de `TOTAL_DU`. Cles sans chevrons (l'appelant ajoute <>).
    """
    total_du = total_du_lignes(lignes)
    total_regle = sum(_ligne_num(l.get("regle")) for l in lignes)
    reste = total_du - total_regle
    return {
        "TOTAL_DU": format_montant(total_du),
        "TOTAL_REGLE": format_montant(total_regle),
        "RESTE_A_PAYER": format_montant(reste),
        "NB_ACTES": str(len(lignes)),
        "TOTAL": format_montant(total_du),
    }


# --- Dents agregees + schema dentaire (schema-dentaire-notes) ------------------
# Balises document derivees des dents des actes retenus : `<DENTS>` (liste FDI
# agregee), `<NB_DENTS>` (compteur) et `<ODONTOGRAMME>` (schema image). Calcul au
# rendu, LECTURE SEULE : n'affecte ni l'acte ni la dette.

def _split_dents(raw) -> list[str]:
    """Decoupe une saisie de dents (FDI) en jetons, comme `repo.normalize_dents`."""
    return [t.strip() for t in re.split(r"[,;\n]+", str(raw or "")) if t.strip()]


def _dents_sort_key(tok: str):
    """Ordre FDI naturel (11,12,...,18,21,...,48,51,...) ; jetons non-FDI en fin."""
    return (0, int(tok)) if repo.is_fdi_valide(tok) else (1, 2 ** 31, tok)


def dents_tries(tokens) -> list[str]:
    """Liste de dents dedupliquee (ordre preserve) puis triee en ordre FDI."""
    seen: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.append(t)
    return sorted(seen, key=_dents_sort_key)


def dents_agregees(lignes: list[dict]) -> list[str]:
    """Ensemble FDI agrege, deduplique et trie des dents de toutes les lignes retenues
    (union mono/multi). Lecture seule (n'ecrit ni `prestations` ni dette)."""
    return dents_tries(t for l in lignes for t in _split_dents(l.get("dents")))


def _ligne_date_fr(iso) -> str:
    """Date d'une ligne ISO -> jj/mm/aaaa (sinon valeur brute)."""
    if not iso:
        return ""
    try:
        return date.fromisoformat(str(iso)).strftime("%d/%m/%Y")
    except ValueError:
        return str(iso)


def _ligne_to_row_repl(l: dict) -> dict[str, str]:
    """Dict de remplacement <L_*> FORMATE d'une ligne, pour l'expansion (D4/D5)."""
    montant = _ligne_num(l.get("montant"))
    regle = _ligne_num(l.get("regle"))
    reste = max(0.0, montant - regle)
    return {
        "<L_DATE>": _ligne_date_fr(l.get("date")),
        "<L_ACTE>": str(l.get("acte") or ""),
        "<L_DENTS>": str(l.get("dents") or ""),
        "<L_NOTE>": str(l.get("note") or ""),
        "<L_MONTANT>": format_montant(montant),
        "<L_REGLE>": format_montant(regle),
        "<L_RESTE>": format_montant(reste),
    }


def get_lignes(variables: dict) -> Optional[list[dict]]:
    """Lignes brutes d'une note multi-lignes depuis `variables` (cle reservee), ou
    None pour un document mono-valeur (compat ascendante, design D7)."""
    lignes = variables.get(LIGNES_KEY)
    return lignes if isinstance(lignes, list) else None


def is_note_autonome(variables: dict) -> bool:
    """Vrai si la note ne reference AUCUN acte — i.e. une note mono-valeur (D2).

    Une note multi-lignes porte toujours la cle `__lignes__` (actes existants ou
    crees a la volee) : elle est donc adossee a des actes et n'est jamais autonome.
    Seule une note autonome engendre une creance « note » a la generation (D1)."""
    return get_lignes(variables) is None


def _variables_of(document: Document) -> dict:
    """Decode `document.variables` (JSON) en dict, tolerant (sinon dict vide)."""
    if not document.variables:
        return {}
    try:
        data = json.loads(document.variables)
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def create_note_creance(
    conn: sqlite3.Connection, document: Document, *,
    is_note: bool, has_actes: bool = False,
) -> Optional["repo.Paiement"]:
    """Cree la creance « note » d'une note AUTONOME a la generation (design D1-D3).

    Une note autonome (sans acte rattache) porte elle-meme le du : on cree un
    `paiement` en_attente rattache au document (`paiements.document_id`), visible page
    Actes/Plans et dans Finances sans nouveau code de lecture (D1).

    Gating strict contre le double-comptage : ne cree rien sauf si `is_note` est vrai
    (un document d'un autre type n'engendre jamais de creance), la note ne reference
    AUCUN acte, `document.montant > 0`, et aucun paiement n'est deja rattache au
    document (idempotence par `document_id`, D3). « Aucun acte » = note multi-lignes
    sans lignes (`is_note_autonome`) **et** aucun acte selectionne/ajoute transmis a la
    generation (`has_actes`) : une note **mono-valeur generee depuis un acte** est donc
    adossee (pas de creance), l'acte restant la source du du. La creance est ensuite
    INDEPENDANTE : regenerer/supprimer la note ne la touche pas (D3).

    Renvoie le paiement cree, ou None si aucune condition n'est remplie (no-op)."""
    if not is_note:
        return None
    if has_actes or not is_note_autonome(_variables_of(document)):
        return None  # note adossee a des actes : le du est porte par les actes
    montant = float(document.montant or 0)
    if montant <= 0:
        return None
    if repo.get_paiement_by_document(conn, document.id) is not None:
        return None  # creance deja creee pour ce document : pas de doublon (D3)
    paiement = repo.create_paiement(
        conn,
        repo.Paiement(
            id=None,
            patient_id=document.patient_id,
            document_id=document.id,
            montant=montant,
            statut="en_attente",
            notes=document.acte or "Note d'honoraires",
            date_echeance=None,
        ),
    )
    repo.log_audit(
        conn, "creance_note_creee",
        {"document_id": document.id, "paiement_id": paiement.id, "montant": montant},
        patient_id=document.patient_id,
    )
    return paiement


def _first_ligne_date(lignes: list[dict]) -> Optional[date]:
    """1re date parseable des lignes (ordre d'affichage), pour acte_date (design D8)."""
    for l in lignes:
        raw = l.get("date")
        if raw:
            try:
                return date.fromisoformat(str(raw))
            except ValueError:
                continue
    return None


def _resume_lignes(lignes: list[dict]) -> Optional[str]:
    """Resume court des actes pour l'affichage liste (ex. « Detartrage, Composite +2 », D8)."""
    labels = [str(l.get("acte") or "").strip() for l in lignes]
    labels = [x for x in labels if x]
    if not labels:
        return None
    head = labels[:2]
    extra = len(labels) - len(head)
    resume = ", ".join(head)
    if extra > 0:
        resume += f" +{extra}"
    return resume


def _draft_fields(variables: dict) -> tuple[date, Optional[float], Optional[str]]:
    """Champs derives (acte_date, montant, acte) : note multi-lignes (D6/D8) sinon
    mono-valeur (historique). Pour une note multi-lignes : montant = total (valeur
    d'affichage/email, **pas** une creance, D6), acte_date = 1re date, acte = resume."""
    lignes = get_lignes(variables)
    if lignes is not None:
        acte_date = _first_ligne_date(lignes) or date.today()
        total = total_du_lignes(lignes)
        return acte_date, (total if total else None), _resume_lignes(lignes)
    return _draft_fields_from_variables(variables)


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

    acte_date, montant, acte = _draft_fields(variables)
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
    acte_date, montant, acte = _draft_fields(variables)
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
    lignes = get_lignes(variables)
    repl = _patient_replacements(patient)
    for tag, raw in variables.items():
        if tag == LIGNES_KEY:
            continue  # lignes traitees a part (expansion de la ligne-modele)
        if tag.upper() in AUTO_PATIENT_TAGS:
            continue  # ne pas ecraser les champs patient
        if tag.upper().startswith("L_"):
            continue  # balise de ligne : remplie par l'expansion, pas en document
        repl.update(_format_variable(tag, raw))

    # Note multi-lignes : totaux calcules (balises document) + lignes formatees
    # (expansion de la ligne-modele). Mono-valeur : `line_rows` reste None (D7).
    line_rows = None
    if lignes is not None:
        repl.update({f"<{k}>": v for k, v in compute_totaux(lignes).items()})
        if "<DATE>" not in repl:  # date d'emission par defaut = aujourd'hui (D1)
            repl["<DATE>"] = date.today().strftime("%d/%m/%Y")
        line_rows = [_ligne_to_row_repl(l) for l in lignes]

    # Dents agregees (texte) + schema dentaire (image), capability schema-dentaire-notes.
    # Source : lignes (note adossee aux actes) sinon le champ DENTS (note mono/autonome
    # pre-rempli depuis l'acte). LECTURE SEULE : aucune ecriture base ni dette.
    if lignes is not None:
        dents = dents_agregees(lignes)
        repl["<DENTS>"] = ", ".join(dents)
        repl["<NB_DENTS>"] = str(len(dents))
    elif variables.get("DENTS") is not None:
        dents = dents_tries(_split_dents(variables.get("DENTS")))
        repl["<DENTS>"] = ", ".join(dents)
        repl["<NB_DENTS>"] = str(len(dents))
    else:
        dents = []

    # Schema dentaire : rendu seulement si le modele porte la balise <ODONTOGRAMME> et
    # qu'au moins une dent est concernee (sinon doc_filler vide la balise, pas d'image).
    images: Optional[dict[str, Path]] = None
    odontogramme_png: Optional[Path] = None
    doc_tags, _ = classify_placeholders(template.path)
    if "ODONTOGRAMME" in doc_tags and dents:
        odontogramme_png = odontogram_render.render_png(dents)
        if odontogramme_png is not None:
            images = {"ODONTOGRAMME": odontogramme_png}

    try:
        with WordSession() as word:
            if ext == "pdf":
                word.fill_and_export_pdf(
                    template.path, repl, out_path, line_rows=line_rows, images=images)
            else:
                with tempfile.TemporaryDirectory() as tmp:
                    pdf_path = Path(tmp) / (out_path.stem + ".pdf")
                    word.fill_and_export_pdf(
                        template.path, repl, pdf_path, line_rows=line_rows, images=images)
                    pdf_first_page_to_jpg(pdf_path, out_path)
    except Exception as exc:  # noqa: BLE001
        document.statut = "erreur"
        document.message_erreur = f"{exc}\n{traceback.format_exc()}"
        repo.update_document(conn, document)
        raise
    finally:
        if odontogramme_png is not None:  # schema temporaire, jamais stocke
            odontogramme_png.unlink(missing_ok=True)

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
