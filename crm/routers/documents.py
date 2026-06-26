"""Routeur documents & generation.

Couvre : la liste des documents d'un patient (onglet Documents de la fiche),
la liste filtree globale (ecran Travaux), le **formulaire de generation** (champs
dynamiques mono-valeur ou editeur multi-lignes), les brouillons, et les operations
longues **rendu / impression / envoi / rafraichissement de statut Mailjet** (Word
+ COM + reseau), executees dans le worker serialise (job + SSE) avec une connexion
SQLite dediee — calque du `jconn` de l'app Flet.

Reutilise `crm/generator.py`, `crm/templates.py`, `crm/printing.py`,
`crm/print_settings.py` et `src/` **sans les modifier**.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from crm import generator, print_settings, printing, repo, templates
from crm import server as core
from crm.db import connect as db_connect
from crm.routers.patients import patient_out, PatientOut

router = APIRouter(prefix="/api", tags=["documents"])

NOTE_CAT_KEY = "note_honoraire_categorie"
NOTE_CAT_DEFAULT = "Notes d'honoraires"


# --- Modeles ------------------------------------------------------------------

class DocumentOut(BaseModel):
    id: int
    patient_id: int
    type: str
    template: Optional[str] = None
    acte: Optional[str] = None
    montant: Optional[float] = None
    acte_date: Optional[str] = None
    output_format: str = "jpg"
    statut: str
    categorie: Optional[str] = None
    date_generation: Optional[str] = None
    date_envoi: Optional[str] = None
    email: Optional[str] = None
    mailjet_status: Optional[str] = None
    mailjet_opened_at: Optional[str] = None
    mailjet_clicked_at: Optional[str] = None
    message_erreur: Optional[str] = None
    has_file: bool = False
    variables: Any = None


class DocumentListOut(BaseModel):
    items: list[DocumentOut]
    total: int


class DocumentRow(BaseModel):
    document: DocumentOut
    patient: PatientOut


class DocumentRowsOut(BaseModel):
    items: list[DocumentRow]
    total: int


class GenFieldOut(BaseModel):
    tag: str
    label: str
    type: str = "text"
    default_value: str = ""
    value: str = ""


class GenActeLine(BaseModel):
    id: int
    libelle: str
    montant: float                  # montant de l'acte (source du du, lecture seule)
    montant_regle: float
    reste: float
    date_acte: Optional[str] = None
    checked: bool = True
    # Montant a facturer sur la note pour cet acte (editable cote UI). Defaut =
    # montant de l'acte ; pour un brouillon, montant edite restitue (D4).
    montant_note: float = 0.0


class GenPlanGroup(BaseModel):
    titre: str
    prestations: list[GenActeLine]


class GenActesSource(BaseModel):
    isoles: list[GenActeLine]
    plans: list[GenPlanGroup]


class GenFormOut(BaseModel):
    template: str
    label: str
    is_multiligne: bool
    output_format: str = "jpg"
    fields: list[GenFieldOut] = []
    actes: Optional[GenActesSource] = None


class GenTemplateOut(BaseModel):
    name: str
    label: str
    categorie: Optional[str] = None
    is_multiligne: bool = False


class NewActeIn(BaseModel):
    libelle: str
    montant: float = 0.0
    acte_id: Optional[int] = None
    date_acte: Optional[str] = None
    dents: Optional[str] = None
    note: Optional[str] = None
    prestation_id: Optional[int] = None  # re-essai : maj au lieu de creer


class DraftIn(BaseModel):
    template: str
    output_format: str = "jpg"
    document_id: Optional[int] = None  # maj d'un brouillon existant
    is_note: bool = False
    variables: dict[str, str] = {}            # modele mono-valeur
    selected_prestation_ids: list[int] = []   # modele multi-lignes : actes existants
    new_actes: list[NewActeIn] = []           # modele multi-lignes : nouveaux actes
    # Montant de note edite par acte retenu (prestation_id -> montant). Affichage
    # seul : pose le `montant` de la ligne sans toucher l'acte (D4). Absent => defaut
    # = montant de l'acte (retro-compatible).
    montants_notes: dict[int, float] = {}


class GenerateIn(DraftIn):
    do_print: bool = False


class SendIn(BaseModel):
    mailjet_template_id: Optional[int] = None


# --- Serialisation ------------------------------------------------------------

def _parse_vars(raw: Optional[str]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def document_out(d: repo.Document) -> DocumentOut:
    has_file = bool(d.file_path and Path(d.file_path).exists())
    return DocumentOut(
        id=d.id, patient_id=d.patient_id, type=d.type, template=d.template,
        acte=d.acte, montant=d.montant, acte_date=d.acte_date,
        output_format=d.output_format, statut=d.statut, categorie=d.categorie,
        date_generation=d.date_generation, date_envoi=d.date_envoi, email=d.email,
        mailjet_status=d.mailjet_status, mailjet_opened_at=d.mailjet_opened_at,
        mailjet_clicked_at=d.mailjet_clicked_at, message_erreur=d.message_erreur,
        has_file=has_file, variables=_parse_vars(d.variables),
    )


# --- Helpers generation (calque app.py, logique independante de l'UI) ---------

def _guess_type(tag: str) -> str:
    t = tag.upper()
    if "DATE" in t:
        return "date"
    if any(k in t for k in ("MONTANT", "PRIX", "TARIF")):
        return "number"
    return "text"


def _humanize(tag: str) -> str:
    return tag.replace("_", " ").strip().capitalize()


def _resolve_fields(conn, template: templates.Template) -> list[repo.TemplateField]:
    """Variables a demander : config enregistree, sinon auto-detection ; exclut les
    balises auto-remplies depuis la fiche patient (NOM, PRENOM, ...) et les balises de
    note derivees (NB_DENTS, ODONTOGRAMME), calculees a la generation.

    Si le modele porte un schema `<ODONTOGRAMME>` (ou `<DENTS>`) mais qu'aucun champ
    `DENTS` n'est present, un champ `DENTS` synthetique est ajoute : c'est lui qui, cote
    frontend, est rendu en bloc de selection FDI et alimente `<DENTS>`/`<NB_DENTS>` et le
    schema (indispensable pour une note autonome ou le modele n'a que `<ODONTOGRAMME>`)."""
    from src.doc_filler import extract_placeholders
    skip = generator.AUTO_PATIENT_TAGS | generator.DERIVED_NOTE_TAGS
    placeholders = extract_placeholders(template.path)  # balises en MAJUSCULES
    saved = repo.list_template_fields(conn, template.name)
    if saved:
        out = [f for f in saved if f.tag.upper() not in skip]
    else:
        out = [repo.TemplateField(template.name, tag, _humanize(tag), _guess_type(tag), "")
               for tag in placeholders if tag not in skip]
    # Champ DENTS synthetique si le modele a un schema/dents sans champ DENTS explicite.
    needs_dents = "ODONTOGRAMME" in placeholders or "DENTS" in placeholders
    if needs_dents and not any(f.tag.upper() == "DENTS" for f in out):
        out.append(repo.TemplateField(template.name, "DENTS", "Dents concernées", "text", ""))
    return out


def _is_multiligne(template: templates.Template) -> bool:
    from src.doc_filler import classify_placeholders
    try:
        _, line_tags = classify_placeholders(template.path)
    except Exception:  # noqa: BLE001
        return False
    return bool(line_tags)


def _cat_eq(a: Optional[str], b: Optional[str]) -> bool:
    return (a or "").strip().casefold() == (b or "").strip().casefold()


def _num_str(value: Optional[float]) -> str:
    """Montant -> chaine pour un champ : entier sans .0, sinon decimal (950, 950.5)."""
    v = float(value or 0)
    return str(int(v)) if v == int(v) else str(v)


def _prefill_from_prestation(tag: str, pres: repo.Prestation) -> Optional[str]:
    """Valeur pré-remplie d'un champ mono-valeur depuis un acte (note depuis 1 acte).

    Mappe par nom de balise standard (ACTE/MONTANT/DATE/DENTS/NOTE) ; renvoie None si
    la balise ne correspond à aucun attribut connu (laissée à la saisie). Les balises
    patient (NOM, …) sont déjà exclues en amont (`_resolve_fields`)."""
    t = tag.upper()
    if t == "ACTE":
        return pres.libelle or ""
    if any(k in t for k in ("MONTANT", "PRIX", "TARIF")):
        return _num_str(pres.montant)
    if "DATE" in t:
        return pres.date_acte or ""  # ISO (le datepicker attend l'ISO)
    if t == "DENTS":
        return pres.dents or ""
    if t == "NOTE":
        return pres.note or ""
    return None


# --- Liste fiche patient ------------------------------------------------------

@router.get("/patients/{patient_id}/documents", response_model=DocumentListOut)
def patient_documents(patient_id: int, limit: Optional[int] = 20,
                      offset: int = 0) -> DocumentListOut:
    with core.db() as conn:
        items = repo.list_documents(conn, patient_id, limit=limit, offset=offset)
        total = repo.count_documents_for_patient(conn, patient_id)
    return DocumentListOut(items=[document_out(d) for d in items], total=total)


# --- Liste globale filtree (Travaux) ------------------------------------------

@router.get("/documents", response_model=DocumentRowsOut)
def documents_filtered(search: str = "", statut: str = "tous",
                       date_from: str = "", date_to: str = "",
                       limit: Optional[int] = 20, offset: int = 0) -> DocumentRowsOut:
    with core.db() as conn:
        rows = repo.list_documents_filtered(conn, search=search, statut=statut,
                                            limit=limit, offset=offset,
                                            date_from=date_from, date_to=date_to)
        total = repo.count_documents_filtered(conn, search=search, statut=statut,
                                              date_from=date_from, date_to=date_to)
    return DocumentRowsOut(
        items=[DocumentRow(document=document_out(d), patient=patient_out(p))
               for d, p in rows],
        total=total,
    )


# --- Formulaire de generation -------------------------------------------------

@router.get("/generation/templates", response_model=list[GenTemplateOut])
def generation_templates(mode: str = "all") -> list[GenTemplateOut]:
    """Modeles proposes selon le mode (calque _generate_dialog) :
    `note` = uniquement la categorie des notes ; `generic` = tout sauf cette
    categorie ; `all` = tout (edition d'un brouillon)."""
    with core.db() as conn:
        note_cat = repo.get_setting(conn, NOTE_CAT_KEY) or NOTE_CAT_DEFAULT
        all_tpls = templates.list_templates()
        out: list[GenTemplateOut] = []
        for t in all_tpls:
            cat = repo.get_template_category(conn, t.name)
            if mode == "note" and not _cat_eq(cat, note_cat):
                continue
            if mode == "generic" and note_cat and _cat_eq(cat, note_cat):
                continue
            # is_multiligne : permet au frontend de pre-selectionner un modele
            # multi-lignes quand on genere une note depuis des actes (page Actes/Plans).
            out.append(GenTemplateOut(name=t.name, label=t.label, categorie=cat,
                                      is_multiligne=_is_multiligne(t)))
    return out


def _acte_line(p: repo.Prestation, checked: bool = True,
               montant_note: Optional[float] = None) -> GenActeLine:
    return GenActeLine(id=p.id, libelle=p.libelle, montant=p.montant,
                       montant_regle=p.montant_regle, reste=p.reste,
                       date_acte=p.date_acte, checked=checked,
                       montant_note=p.montant if montant_note is None else montant_note)


@router.get("/patients/{patient_id}/generation/form", response_model=GenFormOut)
def generation_form(patient_id: int, template: str,
                    document_id: Optional[int] = None,
                    source_prestation_id: Optional[int] = None) -> GenFormOut:
    """Specification du formulaire pour un (patient, modele).

    Mono-valeur : liste des champs a saisir (avec valeurs du brouillon le cas
    echeant ; ou **pre-remplies depuis un acte** si `source_prestation_id` est fourni
    — note generee depuis un acte unique). Multi-lignes : actes existants groupes
    (pre-coches selon le brouillon) pour selection. Les nouveaux actes sont saisis
    cote frontend (carte d'acte).
    """
    with core.db() as conn:
        tpl = templates.get_template(template)
        if tpl is None:
            raise core.ApiError(core.ERR_NOT_FOUND,
                                f"Modèle introuvable : {template}", status=404)
        draft_vars: dict = {}
        out_fmt = "jpg"
        if document_id is not None:
            d = repo.get_document(conn, document_id)
            if d is not None:
                out_fmt = d.output_format or "jpg"
                draft_vars = _parse_vars(d.variables) or {}
        multi = _is_multiligne(tpl)
        if multi:
            saved = draft_vars.get(generator.LIGNES_KEY)
            saved_lines = [l for l in saved if isinstance(l, dict)
                           and l.get("source") == "acte"] \
                if isinstance(saved, list) else None
            saved_ids = {l.get("prestation_id") for l in saved_lines} \
                if saved_lines is not None else None
            # Montant de note edite par acte (restitue a la reouverture du brouillon).
            saved_montants = {l.get("prestation_id"): l.get("montant")
                              for l in (saved_lines or [])
                              if l.get("montant") is not None}
            isoles = repo.list_prestations(conn, patient_id, plan_id=None)
            plans = repo.list_plans(conn, patient_id)

            def checked(pid: int) -> bool:
                return (pid in saved_ids) if saved_ids is not None else True

            def montant_note(pid: int) -> Optional[float]:
                v = saved_montants.get(pid)
                return float(v) if v is not None else None

            groups = []
            for pl in plans:
                pres = repo.list_prestations(conn, patient_id, plan_id=pl.id)
                groups.append(GenPlanGroup(
                    titre=pl.titre,
                    prestations=[_acte_line(x, checked(x.id), montant_note(x.id))
                                 for x in pres]))
            actes = GenActesSource(
                isoles=[_acte_line(x, checked(x.id), montant_note(x.id))
                        for x in isoles], plans=groups)
            return GenFormOut(template=tpl.name, label=tpl.label, is_multiligne=True,
                              output_format=out_fmt, actes=actes)
        # Mono-valeur : valeurs du brouillon en priorité, sinon pré-remplissage depuis
        # l'acte source (note depuis 1 acte), sinon valeur par défaut du champ.
        src_pres = (repo.get_prestation(conn, source_prestation_id)
                    if source_prestation_id and not draft_vars else None)
        fields: list[GenFieldOut] = []
        for f in _resolve_fields(conn, tpl):
            prefill = _prefill_from_prestation(f.tag, src_pres) if src_pres else None
            fallback = prefill if prefill is not None else (f.default_value or "")
            init = draft_vars.get(f.tag, fallback)
            fields.append(GenFieldOut(tag=f.tag, label=f.label or f.tag,
                                      type=f.type, default_value=f.default_value or "",
                                      value=init))
    return GenFormOut(template=tpl.name, label=tpl.label, is_multiligne=False,
                      output_format=out_fmt, fields=fields)


# --- Construction des variables + persistance brouillon -----------------------

def _build_lignes(conn, patient_id: int, body: DraftIn) -> list[dict]:
    """Construit `__lignes__` : actes existants selectionnes + nouveaux actes crees.

    Les nouveaux actes sont crees comme **actes isoles** (plan_id=NULL) — donc
    suivis dans la dette et visibles dans l'onglet Actes (calque Flet). Idempotent :
    un `prestation_id` fourni est mis a jour plutot que recree.

    Le montant de chaque ligne adossee a un acte existant peut etre **surcharge**
    via `body.montants_notes` (affichage seul, D4) : aucune ecriture sur l'acte, qui
    reste la source du du. Defaut (acte non surcharge) = montant de l'acte. Les
    nouveaux actes gardent montant ligne = montant de l'acte (pas de surcharge, D4).
    """
    # Cles JSON normalisees en int (l'objet JSON porte des cles texte ; pydantic
    # coerce deja dict[int, float], on securise les deux formes).
    overrides: dict[int, float] = {}
    for k, v in (body.montants_notes or {}).items():
        try:
            overrides[int(k)] = float(v)
        except (TypeError, ValueError):
            continue
    lignes: list[dict] = []
    for pid in body.selected_prestation_ids:
        pres = repo.get_prestation(conn, pid)
        if pres is not None:
            ligne = generator.prestation_to_ligne(pres)
            if pid in overrides:
                ligne["montant"] = overrides[pid]  # montant de note (affichage, D4)
            lignes.append(ligne)
    for na in body.new_actes:
        if not (na.libelle or "").strip():
            continue
        if na.prestation_id:
            repo.update_prestation(conn, na.prestation_id, libelle=na.libelle.strip(),
                                   montant=na.montant, plan_id=None,
                                   acte_id=na.acte_id, date_acte=na.date_acte,
                                   dents=na.dents, note=na.note)
            pres = repo.get_prestation(conn, na.prestation_id)
        else:
            pres = repo.create_prestation(conn, patient_id, na.libelle.strip(),
                                          na.montant, plan_id=None,
                                          acte_id=na.acte_id, date_acte=na.date_acte,
                                          dents=na.dents, note=na.note)
            repo.log_audit(conn, "acte_cree",
                           {"prestation_id": pres.id, "libelle": pres.libelle,
                            "origine": "note_honoraires"}, patient_id=patient_id)
        lignes.append(generator.prestation_to_ligne(pres))
    return lignes


def _persist_draft(conn, patient_id: int, body: DraftIn) -> repo.Document:
    """Enregistre/maj le brouillon (aucun paiement cree). Renvoie le document."""
    tpl = templates.get_template(body.template)
    if tpl is None:
        raise core.ApiError(core.ERR_NOT_FOUND,
                            f"Modèle introuvable : {body.template}", status=404)
    if _is_multiligne(tpl):
        variables = {generator.LIGNES_KEY: _build_lignes(conn, patient_id, body)}
    else:
        variables = {k: (v or "") for k, v in body.variables.items()}
    if body.document_id is not None:
        draft = repo.get_document(conn, body.document_id)
        if draft is None:
            raise core.ApiError(core.ERR_NOT_FOUND, "Brouillon introuvable.",
                                status=404)
        doc = generator.update_draft(conn, draft, variables=variables,
                                     output_format=body.output_format)
        repo.log_audit(conn, "brouillon_modifie",
                       {"document_id": doc.id, "modele": tpl.name},
                       patient_id=patient_id)
        return doc
    patient = repo.get_patient(conn, patient_id)
    doc = generator.save_draft(conn, patient, tpl, variables=variables,
                               output_format=body.output_format)
    repo.log_audit(conn, "brouillon_cree",
                   {"document_id": doc.id, "modele": tpl.name}, patient_id=patient_id)
    return doc


@router.post("/patients/{patient_id}/documents/draft", response_model=DocumentOut)
def save_draft(patient_id: int, body: DraftIn) -> DocumentOut:
    try:
        with core.db() as conn:
            doc = _persist_draft(conn, patient_id, body)
        return document_out(doc)
    except core.ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)


# --- Operations longues (jobs + SSE) ------------------------------------------

def _check_printer(conn) -> str:
    printer = repo.get_setting(conn, core.PRINTER_KEY)
    if not printer:
        raise core.ApiError(core.ERR_PRINTER_NOT_FOUND,
                            "Aucune imprimante configurée (Paramétrage › Imprimante).",
                            status=400)
    try:
        available = printing.list_printers()
    except Exception:  # noqa: BLE001
        available = []
    if available and printer not in available:
        raise core.ApiError(core.ERR_PRINTER_NOT_FOUND,
                            f"Imprimante « {printer} » indisponible.", status=404)
    return printer


@router.post("/patients/{patient_id}/documents/generate",
             response_model=core.JobAcceptedOut, status_code=202)
def generate(patient_id: int, body: GenerateIn) -> core.JobAcceptedOut:
    """Persiste le brouillon, le rend (Word → JPG/PDF), puis l'imprime si demande.
    Operation longue : 202 + job_id, progression en SSE."""
    # Validation imprimante AVANT de lancer le travail (retour synchrone).
    if body.do_print:
        with core.db() as conn:
            _check_printer(conn)

    def task(report):
        report(0.1, "Préparation du document…")
        conn = db_connect()
        try:
            doc = _persist_draft(conn, patient_id, body)
            report(0.35, "Génération du document (Word)…")
            generator.render_document(conn, doc)
            repo.log_audit(
                conn, "note_honoraires_generee" if body.is_note else "document_genere",
                {"document_id": doc.id, "type": doc.type, "modele": doc.template},
                patient_id=patient_id)
            # Note AUTONOME (sans aucun acte rattache) -> creance « note »
            # (design D1-D3). `has_actes` couvre aussi une note MONO-VALEUR generee
            # depuis un acte (selection/ajout) : elle reste adossee (pas de creance).
            # No-op pour un document d'un autre type ; idempotent si la note est regeneree.
            has_actes = bool(body.selected_prestation_ids or body.new_actes)
            generator.create_note_creance(conn, doc, is_note=body.is_note,
                                          has_actes=has_actes)
            printer = None
            if body.do_print:
                printer = _check_printer(conn)
                report(0.8, f"Impression sur {printer}…")
                cfg = print_settings.get_settings_for(conn, doc.type)
                printing.print_file(Path(doc.file_path or ""), printer,
                                    paper=cfg["paper"], color=cfg["color"])
                repo.log_audit(conn, "document_imprime",
                               {"document_id": doc.id, "imprimante": printer},
                               patient_id=patient_id)
            report(1.0, "Terminé.")
            return {"document_id": doc.id, "printer": printer}
        finally:
            conn.close()

    return core.JobAcceptedOut(job_id=core.submit_job(task))


@router.post("/documents/{document_id}/render", response_model=core.JobAcceptedOut,
             status_code=202)
def render(document_id: int) -> core.JobAcceptedOut:
    def task(report):
        report(0.2, "Génération du document (Word)…")
        conn = db_connect()
        try:
            d = repo.get_document(conn, document_id)
            if d is None:
                raise core.ApiError(core.ERR_NOT_FOUND, "Document introuvable.",
                                    status=404)
            generator.render_document(conn, d)
            report(1.0, "Terminé.")
            return {"document_id": document_id}
        finally:
            conn.close()

    return core.JobAcceptedOut(job_id=core.submit_job(task))


@router.post("/documents/{document_id}/print", response_model=core.JobAcceptedOut,
             status_code=202)
def print_document(document_id: int) -> core.JobAcceptedOut:
    with core.db() as conn:
        printer = _check_printer(conn)
        d = repo.get_document(conn, document_id)
        if d is None:
            raise core.ApiError(core.ERR_NOT_FOUND, "Document introuvable.", status=404)
        doc_type = d.type
        file_path = d.file_path

    def task(report):
        report(0.2, f"Impression sur {printer}…")
        conn = db_connect()
        try:
            cfg = print_settings.get_settings_for(conn, doc_type)
            try:
                printing.print_file(Path(file_path or ""), printer,
                                    paper=cfg["paper"], color=cfg["color"])
            except Exception as exc:  # noqa: BLE001
                raise core.ApiError(core.ERR_PRINT_FAILED,
                                    f"Échec de l'impression : {exc}")
            repo.log_audit(conn, "document_imprime",
                           {"document_id": document_id, "imprimante": printer})
            report(1.0, "Envoyé à l'imprimante.")
            return {"printer": printer}
        finally:
            conn.close()

    return core.JobAcceptedOut(job_id=core.submit_job(task))


@router.post("/documents/{document_id}/send", response_model=core.JobAcceptedOut,
             status_code=202)
def send(document_id: int, body: SendIn) -> core.JobAcceptedOut:
    # Resolution du modele Mailjet AVANT le job (lecture base rapide).
    with core.db() as conn:
        d = repo.get_document(conn, document_id)
        if d is None:
            raise core.ApiError(core.ERR_NOT_FOUND, "Document introuvable.", status=404)
        template_id = body.mailjet_template_id
        if template_id is None:
            default = repo.get_default_mail_template(conn)
            template_id = default.mailjet_template_id if default else None

    def task(report):
        report(0.2, "Envoi de l'email…")
        from src.config import load_config
        conn = db_connect()
        try:
            doc = repo.get_document(conn, document_id)
            config = load_config()
            generator.send_document(conn, doc, config, template_id=template_id)
            report(1.0, "Email envoyé.")
            return {"document_id": document_id}
        finally:
            conn.close()

    return core.JobAcceptedOut(job_id=core.submit_job(task))


@router.post("/documents/{document_id}/refresh-status",
             response_model=core.JobAcceptedOut, status_code=202)
def refresh_status(document_id: int) -> core.JobAcceptedOut:
    def task(report):
        report(0.3, "Interrogation de Mailjet…")
        from src.config import load_config
        conn = db_connect()
        try:
            doc = repo.get_document(conn, document_id)
            if doc is None:
                raise core.ApiError(core.ERR_NOT_FOUND, "Document introuvable.",
                                    status=404)
            status = generator.refresh_mail_status(conn, doc, load_config())
            report(1.0, "Statut mis à jour.")
            return {"status": status}
        finally:
            conn.close()

    return core.JobAcceptedOut(job_id=core.submit_job(task))


@router.post("/documents/{document_id}/open", response_model=core.OkOut)
def open_document(document_id: int) -> core.OkOut:
    """Ouvre le fichier genere avec l'application par defaut (cote machine serveur,
    = poste de l'utilisateur). Calque `_open_file` de l'app Flet."""
    with core.db() as conn:
        d = repo.get_document(conn, document_id)
    if d is None or not d.file_path:
        raise core.ApiError(core.ERR_NOT_FOUND, "Fichier introuvable.", status=404)
    path = Path(d.file_path)
    if not path.exists():
        raise core.ApiError(core.ERR_NOT_FOUND,
                            "Le fichier n'existe plus sur le disque.", status=404)
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:  # pragma: no cover
            import subprocess
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as exc:  # noqa: BLE001
        raise core.ApiError(core.ERR_VALIDATION, f"Ouverture impossible : {exc}")
    return core.OkOut()


@router.delete("/documents/{document_id}", response_model=core.OkOut)
def delete_document(document_id: int) -> core.OkOut:
    with core.db() as conn:
        d = repo.get_document(conn, document_id)
        if d is None:
            raise core.ApiError(core.ERR_NOT_FOUND, "Document introuvable.", status=404)
        # Suppression du fichier sur disque (best-effort) puis de la ligne.
        if d.file_path:
            try:
                p = Path(d.file_path)
                if p.exists():
                    p.unlink()
            except OSError:
                pass
        repo.delete_document(conn, document_id)
        repo.log_audit(conn, "document_supprime", {"document_id": document_id},
                       patient_id=d.patient_id)
    return core.OkOut()
