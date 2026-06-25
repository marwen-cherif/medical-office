"""Couche d'acces aux donnees (patients, documents, paiements).

Expose des dataclasses simples et des fonctions CRUD au-dessus de sqlite3.
"""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional


# --- Utilitaires --------------------------------------------------------------

def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = "".join(c if c.isalnum() else "_" for c in ascii_only.lower())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# --- Reglages applicatifs (table meta, cle/valeur) ----------------------------
# Petits reglages globaux de l'app (ex. imprimante cible). La table `meta` existe
# deja (cf. db.py) et sert aussi au numero de schema : aucune migration requise.

def get_setting(conn: sqlite3.Connection, key: str) -> Optional[str]:
    """Valeur d'un reglage, ou None s'il n'a jamais ete defini."""
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    """Enregistre (ou met a jour) un reglage global."""
    conn.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


# --- Dataclasses --------------------------------------------------------------

@dataclass
class Patient:
    id: Optional[int]
    nom: str
    prenom: str
    date_naissance: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None
    notes: Optional[str] = None

    @property
    def display(self) -> str:
        return f"{self.nom.upper()} {self.prenom}".strip()


@dataclass
class Document:
    id: Optional[int]
    patient_id: int
    type: str
    template: Optional[str] = None
    acte: Optional[str] = None
    montant: Optional[float] = None
    acte_date: Optional[str] = None
    file_path: Optional[str] = None
    output_format: str = "jpg"
    statut: str = "genere"
    date_generation: Optional[str] = None
    date_envoi: Optional[str] = None
    email: Optional[str] = None
    mailjet_message_id: Optional[str] = None
    mailjet_status: Optional[str] = None
    date_refresh_status: Optional[str] = None
    message_erreur: Optional[str] = None
    variables: Optional[str] = None  # JSON des valeurs de variables saisies
    mailjet_opened_at: Optional[str] = None   # 1re ouverture (tracking Mailjet)
    mailjet_clicked_at: Optional[str] = None  # 1er clic (tracking Mailjet)
    categorie: Optional[str] = None  # snapshot de la categorie du modele (v8)


@dataclass
class MailTemplate:
    id: Optional[int]
    name: str
    mailjet_template_id: int
    is_default: bool = False


@dataclass
class TemplateField:
    """Definition d'une variable d'un template de document Word."""
    template_name: str
    tag: str                         # ex. "NB_SEANCES" (sans les chevrons)
    label: str = ""
    type: str = "text"               # text | paragraph | number | date
    default_value: str = ""


@dataclass
class Paiement:
    id: Optional[int]
    patient_id: int
    document_id: Optional[int] = None
    montant: float = 0.0
    montant_regle: float = 0.0
    statut: str = "en_attente"  # en_attente | regle_partiellement | encaisse
    mode: Optional[str] = None
    date_echeance: Optional[str] = None
    date_encaissement: Optional[str] = None
    notes: Optional[str] = None

    @property
    def reste(self) -> float:
        """Reste a recouvrer (>= 0)."""
        return max(0.0, (self.montant or 0) - (self.montant_regle or 0))


@dataclass
class Job:
    """Traitement par lot : 1 job = 1 type de document, generation ou envoi."""
    id: Optional[int]
    kind: str                     # 'generation' | 'envoi'
    doc_type: str
    statut: str = "en_cours"     # en_cours | termine | erreur
    total: int = 0
    done: int = 0
    ok: int = 0
    skipped: int = 0
    errors: int = 0
    params: Optional[str] = None  # JSON
    created_at: Optional[str] = None
    finished_at: Optional[str] = None


@dataclass
class JobItem:
    id: Optional[int]
    job_id: int
    patient_id: Optional[int]
    document_id: Optional[int]
    statut: str                   # ok | skip | erreur
    message: Optional[str] = None
    created_at: Optional[str] = None


# --- Patients -----------------------------------------------------------------

def _row_to_patient(row: sqlite3.Row) -> Patient:
    return Patient(
        id=row["id"],
        nom=row["nom"],
        prenom=row["prenom"],
        date_naissance=row["date_naissance"],
        email=row["email"],
        telephone=row["telephone"],
        adresse=row["adresse"],
        notes=row["notes"],
    )


def create_patient(conn: sqlite3.Connection, p: Patient) -> Patient:
    cur = conn.execute(
        """INSERT INTO patients
           (nom, prenom, slug_nom, slug_prenom, date_naissance, email, telephone, adresse, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            p.nom.strip(),
            p.prenom.strip(),
            slugify(p.nom),
            slugify(p.prenom),
            p.date_naissance,
            p.email,
            p.telephone,
            p.adresse,
            p.notes,
        ),
    )
    conn.commit()
    p.id = cur.lastrowid
    return p


# Champs de la fiche patient suivis dans le journal d'audit (libelle lisible ->
# attribut de la dataclass). Sert au detail avant/apres (cf. diff_patient).
_PATIENT_AUDIT_FIELDS = (
    ("Nom", "nom"),
    ("Prénom", "prenom"),
    ("Date de naissance", "date_naissance"),
    ("Email", "email"),
    ("Téléphone", "telephone"),
    ("Adresse", "adresse"),
    ("Notes", "notes"),
)


def diff_patient(conn: sqlite3.Connection, p: Patient) -> dict[str, list]:
    """Champs reellement modifies entre la fiche en base et `p` (valeurs entrantes).

    Renvoie {libelle: [avant, apres]} ; un champ inchange est exclu. `nom`/`prenom`
    sont normalises (strip) comme a l'ecriture pour ne pas signaler un faux
    changement. Alimente le detail avant/apres du journal (fiche_modifiee).
    """
    old = get_patient(conn, p.id)
    if old is None:
        return {}
    changed: dict[str, list] = {}
    for label, attr in _PATIENT_AUDIT_FIELDS:
        before = getattr(old, attr)
        after = getattr(p, attr)
        if attr in ("nom", "prenom"):
            after = (after or "").strip()
        if (before or "") != (after or ""):
            changed[label] = [before, after]
    return changed


def update_patient(conn: sqlite3.Connection, p: Patient) -> dict[str, list]:
    """Met a jour une fiche patient et renvoie le diff des champs modifies
    ({libelle: [avant, apres]}, calcule AVANT l'UPDATE) pour le journal d'audit.
    Retro-compatible : un appelant qui ignore la valeur de retour fonctionne."""
    changed = diff_patient(conn, p)
    conn.execute(
        """UPDATE patients SET
             nom = ?, prenom = ?, slug_nom = ?, slug_prenom = ?,
             date_naissance = ?, email = ?, telephone = ?, adresse = ?, notes = ?,
             updated_at = ?
           WHERE id = ?""",
        (
            p.nom.strip(),
            p.prenom.strip(),
            slugify(p.nom),
            slugify(p.prenom),
            p.date_naissance,
            p.email,
            p.telephone,
            p.adresse,
            p.notes,
            _now(),
            p.id,
        ),
    )
    conn.commit()
    return changed


def get_patient(conn: sqlite3.Connection, patient_id: int) -> Optional[Patient]:
    row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    return _row_to_patient(row) if row else None


def _patient_filter_clause(search: str, filtre: str) -> tuple[str, list[Any]]:
    """Construit la clause WHERE (et ses parametres) pour la liste des patients.

    `filtre` : "tous" | "email" (avec email) | "impayes" (au moins un paiement
    en attente). `search` cherche dans nom/prenom, insensible aux accents.
    """
    clauses: list[str] = []
    params: list[Any] = []
    if search.strip():
        needle = f"%{slugify(search)}%"
        clauses.append(
            "((slug_nom || '_' || slug_prenom) LIKE ? "
            "OR (slug_prenom || '_' || slug_nom) LIKE ?)"
        )
        params += [needle, needle]
    if filtre == "email":
        clauses.append("email IS NOT NULL AND TRIM(email) <> ''")
    elif filtre == "impayes":
        clauses.append(
            "id IN (SELECT patient_id FROM paiements "
            "WHERE statut IN ('en_attente', 'regle_partiellement'))"
        )
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def list_patients(
    conn: sqlite3.Connection,
    search: str = "",
    filtre: str = "tous",
    limit: int | None = None,
    offset: int = 0,
) -> list[Patient]:
    """Liste paginee/filtree des patients (recherche nom/prenom insensible accents)."""
    where, params = _patient_filter_clause(search, filtre)
    sql = f"SELECT * FROM patients{where} ORDER BY slug_nom, slug_prenom"
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_patient(r) for r in rows]


def count_patients(conn: sqlite3.Connection, search: str = "", filtre: str = "tous") -> int:
    where, params = _patient_filter_clause(search, filtre)
    row = conn.execute(f"SELECT COUNT(*) AS n FROM patients{where}", params).fetchone()
    return int(row["n"])


def count_patients_new(
    conn: sqlite3.Connection, date_from: str = "", date_to: str = ""
) -> int:
    """Patients créés sur la période (tableau de bord), sur `patients.created_at`."""
    clauses: list[str] = []
    params: list[Any] = []
    if date_from.strip():
        clauses.append("date(created_at) >= ?")
        params.append(date_from.strip())
    if date_to.strip():
        clauses.append("date(created_at) <= ?")
        params.append(date_to.strip())
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    row = conn.execute(f"SELECT COUNT(*) AS n FROM patients{where}", params).fetchone()
    return int(row["n"])


def find_matches(conn: sqlite3.Connection, nom: str, prenom: str) -> list[Patient]:
    """Patients potentiellement identiques (meme slug nom+prenom).

    Sert a detecter un doublon avant creation : c'est l'humain qui tranche.
    """
    rows = conn.execute(
        "SELECT * FROM patients WHERE slug_nom = ? AND slug_prenom = ?",
        (slugify(nom), slugify(prenom)),
    ).fetchall()
    return [_row_to_patient(r) for r in rows]


def get_or_create_patient(
    conn: sqlite3.Connection, nom: str, prenom: str, **extra: Any
) -> tuple[Patient, bool]:
    """Renvoie (patient, created). Reutilise un patient au slug identique s'il existe."""
    existing = find_matches(conn, nom, prenom)
    if existing:
        return existing[0], False
    p = Patient(id=None, nom=nom, prenom=prenom, **extra)
    return create_patient(conn, p), True


# --- Documents ----------------------------------------------------------------

def _row_to_document(row: sqlite3.Row) -> Document:
    return Document(
        id=row["id"],
        patient_id=row["patient_id"],
        type=row["type"],
        template=row["template"],
        acte=row["acte"],
        montant=row["montant"],
        acte_date=row["acte_date"],
        file_path=row["file_path"],
        output_format=row["output_format"],
        statut=row["statut"],
        date_generation=row["date_generation"],
        date_envoi=row["date_envoi"],
        email=row["email"],
        mailjet_message_id=row["mailjet_message_id"],
        mailjet_status=row["mailjet_status"],
        date_refresh_status=row["date_refresh_status"],
        message_erreur=row["message_erreur"],
        variables=row["variables"] if "variables" in row.keys() else None,
        mailjet_opened_at=(row["mailjet_opened_at"]
                           if "mailjet_opened_at" in row.keys() else None),
        mailjet_clicked_at=(row["mailjet_clicked_at"]
                            if "mailjet_clicked_at" in row.keys() else None),
        categorie=row["categorie"] if "categorie" in row.keys() else None,
    )


def create_document(conn: sqlite3.Connection, d: Document) -> Document:
    cur = conn.execute(
        """INSERT INTO documents
           (patient_id, type, template, acte, montant, acte_date, file_path,
            output_format, statut, date_generation, date_envoi, email,
            mailjet_message_id, mailjet_status, date_refresh_status, message_erreur,
            variables, categorie)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            d.patient_id, d.type, d.template, d.acte, d.montant, d.acte_date,
            d.file_path, d.output_format, d.statut, d.date_generation, d.date_envoi,
            d.email, d.mailjet_message_id, d.mailjet_status, d.date_refresh_status,
            d.message_erreur, d.variables, d.categorie,
        ),
    )
    conn.commit()
    d.id = cur.lastrowid
    return d


def update_document(conn: sqlite3.Connection, d: Document) -> None:
    conn.execute(
        """UPDATE documents SET
             type=?, template=?, acte=?, montant=?, acte_date=?, file_path=?,
             output_format=?, statut=?, date_generation=?, date_envoi=?, email=?,
             mailjet_message_id=?, mailjet_status=?, date_refresh_status=?, message_erreur=?,
             variables=?, mailjet_opened_at=?, mailjet_clicked_at=?, categorie=?
           WHERE id=?""",
        (
            d.type, d.template, d.acte, d.montant, d.acte_date, d.file_path,
            d.output_format, d.statut, d.date_generation, d.date_envoi, d.email,
            d.mailjet_message_id, d.mailjet_status, d.date_refresh_status,
            d.message_erreur, d.variables, d.mailjet_opened_at, d.mailjet_clicked_at,
            d.categorie, d.id,
        ),
    )
    conn.commit()


def list_documents(
    conn: sqlite3.Connection, patient_id: int,
    limit: int | None = None, offset: int = 0,
) -> list[Document]:
    """Documents d'un patient (recents d'abord). `limit`/`offset` paginent au
    niveau SQL ; sans `limit`, tout l'historique est renvoye (retro-compatible)."""
    sql = "SELECT * FROM documents WHERE patient_id = ? ORDER BY id DESC"
    params: list[Any] = [patient_id]
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_document(r) for r in rows]


def count_documents_for_patient(conn: sqlite3.Connection, patient_id: int) -> int:
    """Nombre total de documents d'un patient (pour la pagination de sa fiche)."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM documents WHERE patient_id = ?", (patient_id,)
    ).fetchone()
    return int(row["n"])


def patient_has_sent_document(conn: sqlite3.Connection, patient_id: int) -> bool:
    """Vrai si le patient a au moins un document envoye et suivi (sans tout charger)."""
    row = conn.execute(
        "SELECT 1 FROM documents WHERE patient_id = ? AND statut = 'envoye' "
        "AND mailjet_message_id IS NOT NULL LIMIT 1",
        (patient_id,),
    ).fetchone()
    return row is not None


def get_document_by_file_path(conn: sqlite3.Connection, file_path: str) -> Optional[Document]:
    row = conn.execute(
        "SELECT * FROM documents WHERE file_path = ? LIMIT 1", (file_path,)
    ).fetchone()
    return _row_to_document(row) if row else None


def get_document(conn: sqlite3.Connection, document_id: int) -> Optional[Document]:
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    return _row_to_document(row) if row else None


def delete_document(conn: sqlite3.Connection, document_id: int) -> None:
    conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
    conn.commit()


# Statuts Mailjet « finaux » : inutile de continuer a interroger l'API ensuite.
MAILJET_FINAL_STATUSES = {
    "clicked", "bounce", "hardbounced", "spam", "unsub", "blocked",
}


def list_pollable_documents(
    conn: sqlite3.Connection, limit: int = 200, recent_days: int = 30
) -> list[Document]:
    """Documents envoyés à re-interroger sur Mailjet (auto-polling).

    Critères : statut 'envoye', message_id présent, statut Mailjet non final, et
    envoyés récemment (borne `recent_days`) pour limiter le volume d'appels API.
    """
    placeholders = ",".join("?" * len(MAILJET_FINAL_STATUSES))
    params: list[Any] = list(MAILJET_FINAL_STATUSES)
    params.append(f"-{recent_days} days")
    params.append(limit)
    rows = conn.execute(
        f"""SELECT * FROM documents
            WHERE statut = 'envoye'
              AND mailjet_message_id IS NOT NULL AND mailjet_message_id <> ''
              AND (mailjet_status IS NULL OR mailjet_status NOT IN ({placeholders}))
              AND (date_envoi IS NULL OR date(date_envoi) >= date('now', ?))
            ORDER BY id DESC LIMIT ?""",
        params,
    ).fetchall()
    return [_row_to_document(r) for r in rows]


# --- Selection par lot (brouillons / documents a envoyer) ---------------------

def list_draft_doc_types(conn: sqlite3.Connection, statuts: list[str]) -> list[str]:
    """Types de documents distincts presents pour les statuts donnes.

    Sert a alimenter le dropdown « type de document » du traitement par lot :
    `["brouillon"]` pour la generation, `["en_attente_envoi", "erreur_envoi"]`
    pour l'envoi.
    """
    if not statuts:
        return []
    placeholders = ",".join("?" * len(statuts))
    rows = conn.execute(
        f"SELECT DISTINCT type FROM documents WHERE statut IN ({placeholders}) "
        "ORDER BY type",
        statuts,
    ).fetchall()
    return [r["type"] for r in rows]


def all_document_types(conn: sqlite3.Connection) -> list[str]:
    """Tous les types de documents distincts deja generes (tous statuts confondus).

    Alimente, avec les noms de modeles, la liste des types reglables dans
    Parametrage > Imprimante (reglages d'impression par type).
    """
    rows = conn.execute(
        "SELECT DISTINCT type FROM documents WHERE type IS NOT NULL AND type <> '' "
        "ORDER BY type"
    ).fetchall()
    return [r["type"] for r in rows]


def _batch_patient_clause(
    search: str,
    doc_type: str,
    statuts: list[str],
    date_from: str = "",
    date_to: str = "",
) -> tuple[str, list[Any]]:
    """Clause WHERE (et parametres) : patients ayant >=1 document du type/statut
    voulus, cree dans l'intervalle (date de creation du document = brouillon)."""
    sub_clauses = ["d.patient_id = patients.id", "d.type = ?"]
    params: list[Any] = [doc_type]
    if statuts:
        sub_clauses.append("d.statut IN (" + ",".join("?" * len(statuts)) + ")")
        params += statuts
    if date_from.strip():
        sub_clauses.append("date(d.created_at) >= ?")
        params.append(date_from.strip())
    if date_to.strip():
        sub_clauses.append("date(d.created_at) <= ?")
        params.append(date_to.strip())
    clauses = ["EXISTS (SELECT 1 FROM documents d WHERE " + " AND ".join(sub_clauses) + ")"]
    if search.strip():
        needle = f"%{slugify(search)}%"
        clauses.append(
            "((slug_nom || '_' || slug_prenom) LIKE ? "
            "OR (slug_prenom || '_' || slug_nom) LIKE ?)"
        )
        params += [needle, needle]
    where = " WHERE " + " AND ".join(clauses)
    return where, params


def list_patients_batch(
    conn: sqlite3.Connection,
    doc_type: str,
    statuts: list[str],
    search: str = "",
    date_from: str = "",
    date_to: str = "",
    limit: int | None = None,
    offset: int = 0,
) -> list[Patient]:
    where, params = _batch_patient_clause(search, doc_type, statuts, date_from, date_to)
    sql = f"SELECT * FROM patients{where} ORDER BY slug_nom, slug_prenom"
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_patient(r) for r in rows]


def count_patients_batch(
    conn: sqlite3.Connection,
    doc_type: str,
    statuts: list[str],
    search: str = "",
    date_from: str = "",
    date_to: str = "",
) -> int:
    where, params = _batch_patient_clause(search, doc_type, statuts, date_from, date_to)
    row = conn.execute(f"SELECT COUNT(*) AS n FROM patients{where}", params).fetchone()
    return int(row["n"])


def list_documents_for_batch(
    conn: sqlite3.Connection,
    patient_id: int,
    doc_type: str,
    statuts: list[str],
    date_from: str = "",
    date_to: str = "",
) -> list[Document]:
    """Documents d'un patient a traiter par un job (memes criteres que le filtre)."""
    clauses = ["patient_id = ?", "type = ?"]
    params: list[Any] = [patient_id, doc_type]
    if statuts:
        clauses.append("statut IN (" + ",".join("?" * len(statuts)) + ")")
        params += statuts
    if date_from.strip():
        clauses.append("date(created_at) >= ?")
        params.append(date_from.strip())
    if date_to.strip():
        clauses.append("date(created_at) <= ?")
        params.append(date_to.strip())
    sql = "SELECT * FROM documents WHERE " + " AND ".join(clauses) + " ORDER BY id"
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_document(r) for r in rows]


def _documents_period_clause(
    statut: Optional[str], date_from: str, date_to: str
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if statut:
        clauses.append("statut = ?")
        params.append(statut)
    if date_from.strip():
        clauses.append("date(created_at) >= ?")
        params.append(date_from.strip())
    if date_to.strip():
        clauses.append("date(created_at) <= ?")
        params.append(date_to.strip())
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def count_documents(
    conn: sqlite3.Connection, statut: Optional[str] = None,
    date_from: str = "", date_to: str = "",
) -> int:
    """Nombre de documents (optionnellement d'un statut) créés sur la période."""
    where, params = _documents_period_clause(statut, date_from, date_to)
    row = conn.execute(f"SELECT COUNT(*) AS n FROM documents{where}", params).fetchone()
    return int(row["n"])


def documents_by_type(
    conn: sqlite3.Connection, date_from: str = "", date_to: str = "",
) -> list[tuple[str, int]]:
    """Répartition (type → nombre) des documents créés sur la période."""
    where, params = _documents_period_clause(None, date_from, date_to)
    rows = conn.execute(
        f"SELECT type, COUNT(*) AS n FROM documents{where} "
        "GROUP BY type ORDER BY n DESC, type",
        params,
    ).fetchall()
    return [(r["type"], int(r["n"])) for r in rows]


def _documents_filter_clause(
    search: str,
    statut: str,
    date_from: str = "",
    date_to: str = "",
) -> tuple[str, list[Any]]:
    """Clause WHERE (et parametres) pour la liste des documents jointe au patient.

    `statut` : une cle de statut exacte (brouillon / genere / en_attente_envoi /
    envoye / erreur / erreur_envoi) ou "tous" (pas de filtre). `search` cherche le
    patient (nom/prenom, insensible aux accents). Le filtre periode porte sur
    `d.created_at` (coherent avec `_documents_period_clause`).
    """
    clauses: list[str] = []
    params: list[Any] = []
    if statut and statut != "tous":
        clauses.append("d.statut = ?")
        params.append(statut)
    if search.strip():
        needle = f"%{slugify(search)}%"
        clauses.append(
            "((pt.slug_nom || '_' || pt.slug_prenom) LIKE ? "
            "OR (pt.slug_prenom || '_' || pt.slug_nom) LIKE ?)"
        )
        params += [needle, needle]
    if date_from.strip():
        clauses.append("date(d.created_at) >= ?")
        params.append(date_from.strip())
    if date_to.strip():
        clauses.append("date(d.created_at) <= ?")
        params.append(date_to.strip())
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def list_documents_filtered(
    conn: sqlite3.Connection,
    search: str = "",
    statut: str = "tous",
    limit: int | None = None,
    offset: int = 0,
    date_from: str = "",
    date_to: str = "",
) -> list[tuple[Document, Patient]]:
    """Liste paginee des documents joints a leur patient, filtree par statut/recherche."""
    where, params = _documents_filter_clause(search, statut, date_from, date_to)
    sql = (
        "SELECT d.*, pt.id AS p_id, pt.nom, pt.prenom, pt.date_naissance, "
        "pt.email AS p_email, pt.telephone, pt.adresse, pt.notes AS p_notes "
        "FROM documents d JOIN patients pt ON pt.id = d.patient_id"
        f"{where} "
        "ORDER BY d.id DESC"
    )
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    rows = conn.execute(sql, params).fetchall()
    out: list[tuple[Document, Patient]] = []
    for r in rows:
        document = _row_to_document(r)
        patient = Patient(
            id=r["p_id"], nom=r["nom"], prenom=r["prenom"],
            date_naissance=r["date_naissance"], email=r["p_email"],
            telephone=r["telephone"], adresse=r["adresse"], notes=r["p_notes"],
        )
        out.append((document, patient))
    return out


def count_documents_filtered(
    conn: sqlite3.Connection,
    search: str = "",
    statut: str = "tous",
    date_from: str = "",
    date_to: str = "",
) -> int:
    where, params = _documents_filter_clause(search, statut, date_from, date_to)
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM documents d "
        f"JOIN patients pt ON pt.id = d.patient_id{where}",
        params,
    ).fetchone()
    return int(row["n"])


def list_document_ids_filtered(
    conn: sqlite3.Connection,
    search: str = "",
    statut: str = "tous",
    date_from: str = "",
    date_to: str = "",
) -> list[int]:
    """Ids de tous les documents du filtre (sans pagination) — pour « Tout sélectionner »."""
    where, params = _documents_filter_clause(search, statut, date_from, date_to)
    rows = conn.execute(
        "SELECT d.id FROM documents d "
        f"JOIN patients pt ON pt.id = d.patient_id{where} ORDER BY d.id DESC",
        params,
    ).fetchall()
    return [int(r["id"]) for r in rows]


# --- Paiements ----------------------------------------------------------------

def _row_to_paiement(row: sqlite3.Row) -> Paiement:
    return Paiement(
        id=row["id"],
        patient_id=row["patient_id"],
        document_id=row["document_id"],
        montant=row["montant"],
        montant_regle=row["montant_regle"],
        statut=row["statut"],
        mode=row["mode"],
        date_echeance=row["date_echeance"],
        date_encaissement=row["date_encaissement"],
        notes=row["notes"],
    )


def get_paiement(conn: sqlite3.Connection, paiement_id: int) -> Optional[Paiement]:
    row = conn.execute(
        "SELECT * FROM paiements WHERE id = ?", (paiement_id,)
    ).fetchone()
    return _row_to_paiement(row) if row else None


def create_paiement(conn: sqlite3.Connection, p: Paiement) -> Paiement:
    # Regle metier : un paiement porte toujours un montant strictement positif.
    if p.montant is None or p.montant <= 0:
        raise ValueError("Le montant d'un paiement doit être strictement supérieur à 0.")
    # Une note creee deja encaissee porte un cumul regle egal au montant.
    montant_regle = float(p.montant_regle or 0)
    if p.statut == "encaisse" and montant_regle <= 0:
        montant_regle = float(p.montant or 0)
    cur = conn.execute(
        """INSERT INTO paiements
           (patient_id, document_id, montant, montant_regle, statut, mode,
            date_echeance, date_encaissement, notes)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            p.patient_id, p.document_id, p.montant, montant_regle, p.statut, p.mode,
            p.date_echeance, p.date_encaissement, p.notes,
        ),
    )
    conn.commit()
    p.id = cur.lastrowid
    p.montant_regle = montant_regle
    return p


def add_paiement_reglement(
    conn: sqlite3.Connection,
    paiement_id: int,
    montant: float,
    *,
    mode: Optional[str] = None,
    date_reglement: Optional[str] = None,
) -> Paiement:
    """Enregistre un versement (partiel ou solde) sur une note. Calque de
    `add_prestation_reglement` : incremente le cumul, derive le statut, historise le
    versement date. `date_encaissement` est posee quand la note est entierement soldee.
    Refuse un montant <= 0 ou superieur au reste a recouvrer."""
    pa = get_paiement(conn, paiement_id)
    if pa is None:
        raise ValueError("Note introuvable.")
    if montant is None or montant <= 0:
        raise ValueError("Le versement doit etre strictement superieur a 0.")
    if montant > pa.reste + 1e-9:
        raise ValueError("Le versement depasse le reste a recouvrer.")
    nouveau = float(pa.montant_regle or 0) + float(montant)
    statut = statut_paiement(float(pa.montant or 0), nouveau)
    when = date_reglement or _now()
    # date_encaissement = date du SOLDE (la note devient 'encaisse') ; reste NULL tant
    # qu'elle est partielle, l'historique date portant alors la tracabilite.
    date_enc = when if statut == "encaisse" else None
    conn.execute(
        "UPDATE paiements SET montant_regle = ?, statut = ?, "
        "date_encaissement = COALESCE(?, date_encaissement), mode = COALESCE(?, mode) "
        "WHERE id = ?",
        (nouveau, statut, date_enc, mode, paiement_id),
    )
    conn.execute(
        "INSERT INTO paiement_reglements (paiement_id, montant, mode, date_reglement) "
        "VALUES (?, ?, ?, ?)",
        (paiement_id, float(montant), mode, when),
    )
    conn.commit()
    return get_paiement(conn, paiement_id)  # type: ignore[return-value]


def mark_paiement_encaisse(
    conn: sqlite3.Connection, paiement_id: int, when: Optional[str] = None,
    mode: Optional[str] = None,
) -> None:
    """Solde ENTIEREMENT une note (raccourci « encaisser » en un clic) : enregistre un
    versement du reste a recouvrer via `add_paiement_reglement` (historise + statut
    'encaisse'). `mode`, s'il est fourni, est enregistre pour la tracabilite.
    """
    pa = get_paiement(conn, paiement_id)
    if pa is None:
        return
    if pa.reste > 1e-9:
        add_paiement_reglement(conn, paiement_id, pa.reste, mode=mode, date_reglement=when)


def list_paiements(
    conn: sqlite3.Connection, patient_id: int,
    limit: int | None = None, offset: int = 0,
) -> list[Paiement]:
    """Paiements d'un patient (recents d'abord). `limit`/`offset` paginent au
    niveau SQL ; sans `limit`, tout l'historique est renvoye (retro-compatible)."""
    sql = "SELECT * FROM paiements WHERE patient_id = ? ORDER BY id DESC"
    params: list[Any] = [patient_id]
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_paiement(r) for r in rows]


def count_paiements_for_patient(conn: sqlite3.Connection, patient_id: int) -> int:
    """Nombre total de paiements d'un patient (pour la pagination de sa fiche)."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM paiements WHERE patient_id = ?", (patient_id,)
    ).fetchone()
    return int(row["n"])


def paiement_has_reglements(conn: sqlite3.Connection, paiement_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM paiement_reglements WHERE paiement_id = ? LIMIT 1",
        (paiement_id,),
    ).fetchone()
    return row is not None


def delete_paiement(conn: sqlite3.Connection, paiement_id: int) -> None:
    """Supprime (annule) une note SANS aucun versement. Une note deja (partiellement)
    reglee n'est pas annulable — sa tresorerie doit rester tracee (calque des actes).
    La trace reste dans le journal d'audit."""
    if paiement_has_reglements(conn, paiement_id):
        raise ValueError(
            "Cette note a deja des reglements : elle ne peut pas etre annulee."
        )
    conn.execute("DELETE FROM paiements WHERE id = ?", (paiement_id,))
    conn.commit()


def _paiement_filter_clause(
    search: str,
    statut: str,
    date_from: str = "",
    date_to: str = "",
) -> tuple[str, list[Any]]:
    """Clause WHERE (et parametres) pour la liste des paiements.

    `statut` : "en_attente" | "encaisse" | "tous". `search` cherche le patient
    (nom/prenom, insensible aux accents).

    Le filtre periode (`date_from`/`date_to`, AAAA-MM-JJ) porte sur une colonne
    date *contextuelle* au statut : la date d'encaissement pour les encaisses
    (tresorerie reelle), la date d'echeance pour les en attente (a recouvrer),
    sinon la date de creation. `date(col)` normalise les timestamps.
    """
    clauses: list[str] = []
    params: list[Any] = []
    if statut in ("en_attente", "encaisse"):
        clauses.append("pa.statut = ?")
        params.append(statut)
    if search.strip():
        needle = f"%{slugify(search)}%"
        clauses.append(
            "((pt.slug_nom || '_' || pt.slug_prenom) LIKE ? "
            "OR (pt.slug_prenom || '_' || pt.slug_nom) LIKE ?)"
        )
        params += [needle, needle]
    date_col = {
        "encaisse": "pa.date_encaissement",
        "en_attente": "pa.date_echeance",
    }.get(statut, "pa.created_at")
    if date_from.strip():
        clauses.append(f"date({date_col}) >= ?")
        params.append(date_from.strip())
    if date_to.strip():
        clauses.append(f"date({date_col}) <= ?")
        params.append(date_to.strip())
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def list_paiements_filtered(
    conn: sqlite3.Connection,
    search: str = "",
    statut: str = "en_attente",
    limit: int | None = None,
    offset: int = 0,
    date_from: str = "",
    date_to: str = "",
) -> list[tuple[Paiement, Patient]]:
    """Liste paginee des paiements joints a leur patient, filtree par statut/recherche."""
    where, params = _paiement_filter_clause(search, statut, date_from, date_to)
    sql = (
        "SELECT pa.*, pt.id AS p_id, pt.nom, pt.prenom, pt.date_naissance, "
        "pt.email, pt.telephone, pt.adresse, pt.notes "
        "FROM paiements pa JOIN patients pt ON pt.id = pa.patient_id"
        f"{where} "
        "ORDER BY pa.date_echeance IS NULL, pa.date_echeance, pa.id DESC"
    )
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    rows = conn.execute(sql, params).fetchall()
    out: list[tuple[Paiement, Patient]] = []
    for r in rows:
        paiement = _row_to_paiement(r)
        patient = Patient(
            id=r["p_id"], nom=r["nom"], prenom=r["prenom"],
            date_naissance=r["date_naissance"], email=r["email"],
            telephone=r["telephone"], adresse=r["adresse"], notes=r["notes"],
        )
        out.append((paiement, patient))
    return out


def count_paiements(
    conn: sqlite3.Connection,
    search: str = "",
    statut: str = "en_attente",
    date_from: str = "",
    date_to: str = "",
) -> int:
    where, params = _paiement_filter_clause(search, statut, date_from, date_to)
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM paiements pa "
        f"JOIN patients pt ON pt.id = pa.patient_id{where}",
        params,
    ).fetchone()
    return int(row["n"])


def total_paiements(
    conn: sqlite3.Connection,
    search: str = "",
    statut: str = "en_attente",
    date_from: str = "",
    date_to: str = "",
) -> float:
    where, params = _paiement_filter_clause(search, statut, date_from, date_to)
    row = conn.execute(
        "SELECT COALESCE(SUM(pa.montant), 0) AS total FROM paiements pa "
        f"JOIN patients pt ON pt.id = pa.patient_id{where}",
        params,
    ).fetchone()
    return float(row["total"] or 0)


# --- Modeles d'email (Mailjet) ------------------------------------------------

def _row_to_mail_template(row: sqlite3.Row) -> MailTemplate:
    return MailTemplate(
        id=row["id"],
        name=row["name"],
        mailjet_template_id=row["mailjet_template_id"],
        is_default=bool(row["is_default"]),
    )


def list_mail_templates(conn: sqlite3.Connection) -> list[MailTemplate]:
    rows = conn.execute(
        "SELECT * FROM mail_templates ORDER BY is_default DESC, name"
    ).fetchall()
    return [_row_to_mail_template(r) for r in rows]


def get_default_mail_template(conn: sqlite3.Connection) -> Optional[MailTemplate]:
    row = conn.execute(
        "SELECT * FROM mail_templates ORDER BY is_default DESC, id LIMIT 1"
    ).fetchone()
    return _row_to_mail_template(row) if row else None


def create_mail_template(conn: sqlite3.Connection, t: MailTemplate) -> MailTemplate:
    cur = conn.execute(
        "INSERT INTO mail_templates (name, mailjet_template_id, is_default) VALUES (?,?,?)",
        (t.name.strip(), t.mailjet_template_id, int(t.is_default)),
    )
    conn.commit()
    t.id = cur.lastrowid
    if t.is_default:
        set_default_mail_template(conn, t.id)
    return t


def update_mail_template(conn: sqlite3.Connection, t: MailTemplate) -> None:
    conn.execute(
        "UPDATE mail_templates SET name=?, mailjet_template_id=?, is_default=? WHERE id=?",
        (t.name.strip(), t.mailjet_template_id, int(t.is_default), t.id),
    )
    conn.commit()
    if t.is_default and t.id is not None:
        set_default_mail_template(conn, t.id)


def delete_mail_template(conn: sqlite3.Connection, template_id: int) -> None:
    conn.execute("DELETE FROM mail_templates WHERE id=?", (template_id,))
    conn.commit()


def set_default_mail_template(conn: sqlite3.Connection, template_id: int) -> None:
    conn.execute("UPDATE mail_templates SET is_default = (id = ?)", (template_id,))
    conn.commit()


# --- Variables des templates de document --------------------------------------

def list_template_fields(conn: sqlite3.Connection, template_name: str) -> list[TemplateField]:
    rows = conn.execute(
        "SELECT * FROM template_fields WHERE template_name = ? ORDER BY sort_order, id",
        (template_name,),
    ).fetchall()
    return [
        TemplateField(
            template_name=r["template_name"],
            tag=r["tag"],
            label=r["label"] or "",
            type=r["type"] or "text",
            default_value=r["default_value"] or "",
        )
        for r in rows
    ]


def replace_template_fields(
    conn: sqlite3.Connection, template_name: str, fields: list[TemplateField]
) -> None:
    """Remplace en bloc la configuration des variables d'un template."""
    conn.execute("DELETE FROM template_fields WHERE template_name = ?", (template_name,))
    for order, f in enumerate(fields):
        conn.execute(
            """INSERT INTO template_fields
               (template_name, tag, label, type, default_value, sort_order)
               VALUES (?,?,?,?,?,?)""",
            (template_name, f.tag, f.label, f.type, f.default_value, order),
        )
    conn.commit()


# --- Categories de modeles (v8) -----------------------------------------------
# La categorie est un attribut de MODELE (texte libre, saisi dans l'app, pas dans
# le .docx) ; voir openspec/changes/organize-documents-by-category. Trois points de
# persistance : `template_meta` (modele -> categorie courante), `categories`
# (couleur/icone/ordre par categorie, creee paresseusement) et `documents.categorie`
# (snapshot fige a la generation, gere par create/update_document ci-dessus).

# Palette par defaut attribuee cycliquement aux nouvelles categories (cf. _card/UI :
# couleurs lisibles sur fond clair). Cosmetique, modifiable ensuite via upsert_category.
_CATEGORY_PALETTE = (
    "#10357F", "#0C8B82", "#B45309", "#1E7E45",
    "#B5271B", "#6D28D9", "#0E7490", "#A16207",
)


@dataclass
class Category:
    nom: str
    couleur: Optional[str] = None
    icone: Optional[str] = None
    sort_order: int = 0


def _row_to_category(row: sqlite3.Row) -> Category:
    return Category(
        nom=row["nom"],
        couleur=row["couleur"],
        icone=row["icone"],
        sort_order=row["sort_order"],
    )


def list_categories(conn: sqlite3.Connection) -> list[Category]:
    """Toutes les categories connues (suggestions + regroupement), triees."""
    rows = conn.execute(
        "SELECT * FROM categories ORDER BY sort_order, nom"
    ).fetchall()
    return [_row_to_category(r) for r in rows]


def get_category(conn: sqlite3.Connection, nom: str) -> Optional[Category]:
    row = conn.execute(
        "SELECT * FROM categories WHERE nom = ?", ((nom or "").strip(),)
    ).fetchone()
    return _row_to_category(row) if row else None


def _default_category_color(conn: sqlite3.Connection) -> str:
    """Couleur par defaut d'une nouvelle categorie (cyclique sur la palette)."""
    n = conn.execute("SELECT COUNT(*) AS n FROM categories").fetchone()["n"]
    return _CATEGORY_PALETTE[int(n) % len(_CATEGORY_PALETTE)]


def upsert_category(conn: sqlite3.Connection, cat: Category) -> Category:
    """Cree (avec couleur par defaut si absente) ou met a jour une categorie.

    Creation paresseuse : appelee chaque fois qu'un nom de categorie nouveau
    apparait. Sur une categorie existante, couleur/icone ne sont ecrasees que si
    explicitement fournies (non None) — ne pas perdre la couleur en re-confirmant
    simplement l'existence du nom.
    """
    nom = (cat.nom or "").strip()
    if not nom:
        raise ValueError("Le nom d'une categorie ne peut pas etre vide.")
    existing = get_category(conn, nom)
    if existing is None:
        couleur = cat.couleur or _default_category_color(conn)
        conn.execute(
            "INSERT INTO categories (nom, couleur, icone, sort_order) VALUES (?,?,?,?)",
            (nom, couleur, cat.icone, cat.sort_order or 0),
        )
    else:
        conn.execute(
            "UPDATE categories SET couleur = COALESCE(?, couleur), "
            "icone = COALESCE(?, icone), sort_order = ? WHERE nom = ?",
            (cat.couleur, cat.icone, cat.sort_order or existing.sort_order, nom),
        )
    conn.commit()
    return get_category(conn, nom)  # type: ignore[return-value]


def get_template_category(conn: sqlite3.Connection, template_name: str) -> Optional[str]:
    """Categorie courante d'un modele, ou None s'il n'en a pas."""
    row = conn.execute(
        "SELECT categorie FROM template_meta WHERE template_name = ?",
        (template_name,),
    ).fetchone()
    cat = row["categorie"] if row else None
    return cat if (cat or "").strip() else None


def set_template_category(
    conn: sqlite3.Connection, template_name: str, categorie: Optional[str]
) -> None:
    """Associe (ou dissocie) une categorie a un modele.

    `categorie` vide/None => suppression de la ligne `template_meta` (modele sans
    categorie). Sinon : upsert de la ligne et creation paresseuse de la categorie.
    """
    cat = (categorie or "").strip()
    if not cat:
        conn.execute(
            "DELETE FROM template_meta WHERE template_name = ?", (template_name,)
        )
        conn.commit()
        return
    upsert_category(conn, Category(nom=cat))
    conn.execute(
        "INSERT INTO template_meta (template_name, categorie) VALUES (?, ?) "
        "ON CONFLICT(template_name) DO UPDATE SET categorie = excluded.categorie",
        (template_name, cat),
    )
    conn.commit()


def rename_template_meta(
    conn: sqlite3.Connection, ancien_nom: str, nouveau_nom: str
) -> None:
    """Reporte la ligne `template_meta` lors du renommage d'un modele.

    Evite d'orpheliner la categorie du modele renomme. `template_fields` reste,
    lui, orphelin (limitation existante non corrigee ici).
    """
    if ancien_nom == nouveau_nom:
        return
    row = conn.execute(
        "SELECT categorie FROM template_meta WHERE template_name = ?", (ancien_nom,)
    ).fetchone()
    if row is None:
        return
    conn.execute("DELETE FROM template_meta WHERE template_name = ?", (ancien_nom,))
    conn.execute(
        "INSERT INTO template_meta (template_name, categorie) VALUES (?, ?) "
        "ON CONFLICT(template_name) DO UPDATE SET categorie = excluded.categorie",
        (nouveau_nom, row["categorie"]),
    )
    conn.commit()


def rename_category(
    conn: sqlite3.Connection,
    ancien: str,
    nouveau: str,
    *,
    reclasser_documents: bool = False,
) -> list[Document]:
    """Renomme une categorie partout (transactionnel).

    - renomme la ligne `categories` (couleur/icone conservees ; fusion si la cible
      existe deja) ;
    - met a jour tous les `template_meta` portant l'ancien nom ;
    - si `reclasser_documents` : met aussi a jour `documents.categorie`.

    Renvoie la liste des documents reclasses (avec leur `file_path` AVANT mise a
    jour) pour que l'appelant deplace leurs fichiers HORS transaction (cf.
    `generator.move_documents_to_category`). Liste vide si `reclasser_documents`
    est faux.
    """
    ancien = (ancien or "").strip()
    nouveau = (nouveau or "").strip()
    if not nouveau:
        raise ValueError("Le nouveau nom de categorie ne peut pas etre vide.")
    if ancien == nouveau:
        return []
    reclasses: list[Document] = []
    with conn:  # transaction : commit a la sortie, rollback si exception
        if reclasser_documents:
            rows = conn.execute(
                "SELECT * FROM documents WHERE categorie = ?", (ancien,)
            ).fetchall()
            reclasses = [_row_to_document(r) for r in rows]
        target = conn.execute(
            "SELECT nom FROM categories WHERE nom = ?", (nouveau,)
        ).fetchone()
        if target is None:
            conn.execute(
                "UPDATE categories SET nom = ? WHERE nom = ?", (nouveau, ancien)
            )
        else:
            # La cible porte deja sa couleur/icone : on retire l'ancienne ligne.
            conn.execute("DELETE FROM categories WHERE nom = ?", (ancien,))
        conn.execute(
            "UPDATE template_meta SET categorie = ? WHERE categorie = ?",
            (nouveau, ancien),
        )
        if reclasser_documents:
            conn.execute(
                "UPDATE documents SET categorie = ? WHERE categorie = ?",
                (nouveau, ancien),
            )
    return reclasses


# --- Referentiel d'actes (v9) -------------------------------------------------
# Catalogue d'actes tarifes (libelle + prix) : source de prix reutilisable pour
# pre-remplir des montants ailleurs (plans de traitement, facturation multi-lignes).
# Cle technique `id` (et NON le libelle, contrairement a `categories`) : un libelle
# peut etre edite, mais un referencement historique doit rester stable. Retrait NON
# destructif via `actif`. La CONSOMMATION (snapshot du prix par les appelants) est
# hors perimetre ici : ce module n'expose que la lecture. Voir
# openspec/changes/referentiel-actes.

@dataclass
class Acte:
    id: Optional[int]
    libelle: str
    prix: float = 0.0
    code: Optional[str] = None
    actif: bool = True
    sort_order: int = 0


def _row_to_acte(row: sqlite3.Row) -> Acte:
    return Acte(
        id=row["id"],
        libelle=row["libelle"],
        prix=row["prix"],
        code=row["code"],
        actif=bool(row["actif"]),
        sort_order=row["sort_order"],
    )


def create_acte(conn: sqlite3.Connection, a: Acte) -> Acte:
    """Cree un acte. Libelle obligatoire (non vide), prix >= 0, actif par defaut."""
    libelle = (a.libelle or "").strip()
    if not libelle:
        raise ValueError("Le libelle d'un acte est obligatoire.")
    if a.prix is None or a.prix < 0:
        raise ValueError("Le prix d'un acte doit etre positif ou nul.")
    cur = conn.execute(
        """INSERT INTO actes (libelle, slug_libelle, prix, code, actif, sort_order)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (libelle, slugify(libelle), float(a.prix), (a.code or None),
         int(a.actif), a.sort_order or 0),
    )
    conn.commit()
    a.id = cur.lastrowid
    a.libelle = libelle
    return a


def update_acte(conn: sqlite3.Connection, a: Acte) -> None:
    """Met a jour libelle/slug/prix/code/ordre. Le changement de prix n'affecte que
    les usages FUTURs : un montant deja recopie ailleurs (snapshot) n'est pas touche."""
    libelle = (a.libelle or "").strip()
    if not libelle:
        raise ValueError("Le libelle d'un acte est obligatoire.")
    if a.prix is None or a.prix < 0:
        raise ValueError("Le prix d'un acte doit etre positif ou nul.")
    conn.execute(
        """UPDATE actes SET libelle = ?, slug_libelle = ?, prix = ?, code = ?,
             sort_order = ? WHERE id = ?""",
        (libelle, slugify(libelle), float(a.prix), (a.code or None),
         a.sort_order or 0, a.id),
    )
    conn.commit()


def set_acte_actif(conn: sqlite3.Connection, acte_id: int, actif: bool) -> None:
    """Active/desactive un acte (retrait NON destructif). Un acte inactif disparait
    des listes de saisie par defaut mais reste en base et peut etre reactive."""
    conn.execute("UPDATE actes SET actif = ? WHERE id = ?", (int(actif), acte_id))
    conn.commit()


def delete_acte(conn: sqlite3.Connection, acte_id: int) -> None:
    """Suppression DURE, reservee a un acte jamais utilise (decision de l'appelant).
    Le retrait courant passe par set_acte_actif (desactivation), non destructif."""
    conn.execute("DELETE FROM actes WHERE id = ?", (acte_id,))
    conn.commit()


def get_acte(conn: sqlite3.Connection, acte_id: int) -> Optional[Acte]:
    """Lookup d'un acte par id : contrat de lecture pour le pre-remplissage.

    Un consommateur (etape de plan, ligne de facture) lit l'acte et recopie son
    couple (libelle, prix) au moment de l'usage ; ce module ne pre-remplit rien.
    """
    row = conn.execute("SELECT * FROM actes WHERE id = ?", (acte_id,)).fetchone()
    return _row_to_acte(row) if row else None


def find_acte_by_libelle(
    conn: sqlite3.Connection, libelle: str, exclude_id: Optional[int] = None
) -> Optional[Acte]:
    """Acte ACTIF au libelle identique (insensible accents/casse), s'il existe.

    Alimente l'avertissement NON bloquant de doublon a la creation/edition.
    `exclude_id` ignore l'acte en cours d'edition (pour ne pas s'auto-signaler).
    """
    slug = slugify(libelle)
    if not slug:
        return None
    sql = "SELECT * FROM actes WHERE slug_libelle = ? AND actif = 1"
    params: list[Any] = [slug]
    if exclude_id is not None:
        sql += " AND id <> ?"
        params.append(exclude_id)
    sql += " ORDER BY id LIMIT 1"
    row = conn.execute(sql, params).fetchone()
    return _row_to_acte(row) if row else None


def _acte_filter_clause(search: str, actifs_seulement: bool) -> tuple[str, list[Any]]:
    """Clause WHERE (et parametres) pour la liste des actes.

    `search` cherche le libelle, insensible aux accents (slug + LIKE, comme
    patients/documents). `actifs_seulement` exclut les actes desactives.
    """
    clauses: list[str] = []
    params: list[Any] = []
    if actifs_seulement:
        clauses.append("actif = 1")
    if search.strip():
        clauses.append("slug_libelle LIKE ?")
        params.append(f"%{slugify(search)}%")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def list_actes(
    conn: sqlite3.Connection,
    search: str = "",
    actifs_seulement: bool = True,
    limit: int | None = None,
    offset: int = 0,
) -> list[Acte]:
    """Liste paginee/filtree des actes (recherche libelle insensible accents).

    Contrat de lecture reutilisable : un consommateur y choisit un acte dont il
    recopie (snapshot) le couple (libelle, prix). Tri `sort_order, slug_libelle`.
    """
    where, params = _acte_filter_clause(search, actifs_seulement)
    sql = f"SELECT * FROM actes{where} ORDER BY sort_order, slug_libelle"
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_acte(r) for r in rows]


def count_actes(
    conn: sqlite3.Connection, search: str = "", actifs_seulement: bool = True
) -> int:
    where, params = _acte_filter_clause(search, actifs_seulement)
    row = conn.execute(f"SELECT COUNT(*) AS n FROM actes{where}", params).fetchone()
    return int(row["n"])


# --- Jobs (traitement par lot) ------------------------------------------------

def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        kind=row["kind"],
        doc_type=row["doc_type"],
        statut=row["statut"],
        total=row["total"],
        done=row["done"],
        ok=row["ok"],
        skipped=row["skipped"],
        errors=row["errors"],
        params=row["params"],
        created_at=row["created_at"],
        finished_at=row["finished_at"],
    )


def _row_to_job_item(row: sqlite3.Row) -> JobItem:
    return JobItem(
        id=row["id"],
        job_id=row["job_id"],
        patient_id=row["patient_id"],
        document_id=row["document_id"],
        statut=row["statut"],
        message=row["message"],
        created_at=row["created_at"],
    )


def create_job(
    conn: sqlite3.Connection, kind: str, doc_type: str, total: int,
    params: Optional[str] = None,
) -> Job:
    cur = conn.execute(
        "INSERT INTO jobs (kind, doc_type, statut, total, params) "
        "VALUES (?,?,?,?,?)",
        (kind, doc_type, "en_cours", total, params),
    )
    conn.commit()
    return get_job(conn, cur.lastrowid)  # type: ignore[return-value]


def add_job_item(
    conn: sqlite3.Connection, job_id: int, patient_id: Optional[int],
    statut: str, document_id: Optional[int] = None, message: Optional[str] = None,
) -> None:
    """Ajoute une ligne de detail et incremente les compteurs du job en une fois."""
    conn.execute(
        "INSERT INTO job_items (job_id, patient_id, document_id, statut, message) "
        "VALUES (?,?,?,?,?)",
        (job_id, patient_id, document_id, statut, message),
    )
    col = {"ok": "ok", "skip": "skipped", "erreur": "errors"}.get(statut)
    inc = f", {col} = {col} + 1" if col else ""
    conn.execute(
        f"UPDATE jobs SET done = done + 1{inc} WHERE id = ?",
        (job_id,),
    )
    conn.commit()


def finish_job(conn: sqlite3.Connection, job_id: int, statut: str = "termine") -> None:
    conn.execute(
        "UPDATE jobs SET statut = ?, finished_at = ? WHERE id = ?",
        (statut, _now(), job_id),
    )
    conn.commit()


def get_job(conn: sqlite3.Connection, job_id: int) -> Optional[Job]:
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_job(row) if row else None


def _jobs_period_clause(date_from: str, date_to: str) -> tuple[str, list[Any]]:
    """Clause WHERE (periode sur jobs.created_at) pour la liste des travaux."""
    clauses: list[str] = []
    params: list[Any] = []
    if date_from.strip():
        clauses.append("date(created_at) >= ?")
        params.append(date_from.strip())
    if date_to.strip():
        clauses.append("date(created_at) <= ?")
        params.append(date_to.strip())
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def list_jobs(
    conn: sqlite3.Connection, limit: int | None = None, offset: int = 0,
    date_from: str = "", date_to: str = "",
) -> list[Job]:
    where, params = _jobs_period_clause(date_from, date_to)
    sql = f"SELECT * FROM jobs{where} ORDER BY id DESC"
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_job(r) for r in rows]


def count_jobs(
    conn: sqlite3.Connection, date_from: str = "", date_to: str = ""
) -> int:
    where, params = _jobs_period_clause(date_from, date_to)
    row = conn.execute(f"SELECT COUNT(*) AS n FROM jobs{where}", params).fetchone()
    return int(row["n"])


def list_job_items(conn: sqlite3.Connection, job_id: int) -> list[JobItem]:
    rows = conn.execute(
        "SELECT * FROM job_items WHERE job_id = ? ORDER BY id", (job_id,)
    ).fetchall()
    return [_row_to_job_item(r) for r in rows]


def list_failed_job_items(conn: sqlite3.Connection, job_id: int) -> list[JobItem]:
    """Lignes en erreur d'un job (avec document_id) pour relancer precisement les echecs."""
    rows = conn.execute(
        "SELECT * FROM job_items WHERE job_id = ? AND statut = 'erreur' "
        "AND document_id IS NOT NULL ORDER BY id",
        (job_id,),
    ).fetchall()
    return [_row_to_job_item(r) for r in rows]


def mark_stale_jobs_interrupted(conn: sqlite3.Connection) -> int:
    """Au demarrage : un job 'en_cours' ne peut survivre a la fermeture de l'app
    (thread perdu). On le marque 'interrompu'. A NE PAS appeler depuis le thread
    d'un job en cours (il s'auto-marquerait). Renvoie le nombre de jobs corriges."""
    cur = conn.execute(
        "UPDATE jobs SET statut = 'interrompu', finished_at = ? "
        "WHERE statut = 'en_cours'",
        (_now(),),
    )
    conn.commit()
    return cur.rowcount


# --- Journal d'audit ----------------------------------------------------------

def log_audit(
    conn: sqlite3.Connection, action: str, detail: Any = "",
    *, patient_id: Optional[int] = None,
) -> None:
    """Consigne une action (best-effort : ne jamais faire echouer l'appelant).

    `detail` peut etre une chaine (retro-compat) ou un dict/list : dans ce dernier
    cas il est serialise en JSON (cf. parse_audit_detail pour la lecture tolerante).
    `patient_id` rattache l'evenement a une fiche (None = evenement global, ex.
    demarrage) ; il alimente l'onglet Historique via list_audit_patient.
    """
    try:
        if isinstance(detail, (dict, list)):
            detail_str = json.dumps(detail, ensure_ascii=False)
        else:
            detail_str = str(detail) if detail else ""
        conn.execute(
            "INSERT INTO audit_log (action, detail, patient_id) VALUES (?, ?, ?)",
            (action, detail_str, patient_id),
        )
        conn.commit()
    except sqlite3.Error:
        pass


def parse_audit_detail(detail: str) -> Any:
    """Decode le `detail` d'un evenement : objet JSON si possible, sinon la chaine
    brute (anciennes lignes non structurees). Best-effort : ne leve jamais."""
    if not detail:
        return None
    try:
        return json.loads(detail)
    except (ValueError, TypeError):
        return detail


def list_audit(
    conn: sqlite3.Connection, limit: int | None = None,
    date_from: str = "", date_to: str = "",
) -> list[tuple[str, str, str]]:
    """Renvoie (ts, action, detail) les plus recents, optionnellement sur une periode."""
    clauses: list[str] = []
    params: list[Any] = []
    if date_from.strip():
        clauses.append("date(ts) >= ?")
        params.append(date_from.strip())
    if date_to.strip():
        clauses.append("date(ts) <= ?")
        params.append(date_to.strip())
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT ts, action, detail FROM audit_log{where} ORDER BY id DESC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [(r["ts"], r["action"], r["detail"] or "") for r in rows]


def list_audit_patient(
    conn: sqlite3.Connection, patient_id: int, limit: int = 200,
) -> list[tuple[str, str, str]]:
    """Evenements d'un patient, du plus recent au plus ancien (onglet Historique).

    Renvoie (ts, action, detail) ; `detail` est la chaine brute (JSON pour les
    lignes recentes), a decoder via parse_audit_detail cote presentation.
    """
    rows = conn.execute(
        "SELECT ts, action, detail FROM audit_log WHERE patient_id = ? "
        "ORDER BY id DESC LIMIT ?",
        (patient_id, limit),
    ).fetchall()
    return [(r["ts"], r["action"], r["detail"] or "") for r in rows]


# =============================================================================
# Depenses fournisseurs (v6) : prestataires, factures importees, depenses.
# Calque des patrons patients/paiements ci-dessus ; `documents` n'est pas touchee.
# =============================================================================

# --- Prestataires (calque de Patient) -----------------------------------------

@dataclass
class Prestataire:
    id: Optional[int]
    nom: str
    prenom: str = ""
    email: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None
    notes: Optional[str] = None

    @property
    def display(self) -> str:
        return f"{self.nom.upper()} {self.prenom}".strip()


def _row_to_prestataire(row: sqlite3.Row) -> Prestataire:
    return Prestataire(
        id=row["id"],
        nom=row["nom"],
        prenom=row["prenom"],
        email=row["email"],
        telephone=row["telephone"],
        adresse=row["adresse"],
        notes=row["notes"],
    )


def create_prestataire(conn: sqlite3.Connection, p: Prestataire) -> Prestataire:
    cur = conn.execute(
        """INSERT INTO prestataires
           (nom, prenom, slug_nom, slug_prenom, email, telephone, adresse, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            p.nom.strip(),
            (p.prenom or "").strip(),
            slugify(p.nom),
            slugify(p.prenom or ""),
            p.email,
            p.telephone,
            p.adresse,
            p.notes,
        ),
    )
    conn.commit()
    p.id = cur.lastrowid
    return p


def update_prestataire(conn: sqlite3.Connection, p: Prestataire) -> None:
    conn.execute(
        """UPDATE prestataires SET
             nom = ?, prenom = ?, slug_nom = ?, slug_prenom = ?,
             email = ?, telephone = ?, adresse = ?, notes = ?, updated_at = ?
           WHERE id = ?""",
        (
            p.nom.strip(),
            (p.prenom or "").strip(),
            slugify(p.nom),
            slugify(p.prenom or ""),
            p.email,
            p.telephone,
            p.adresse,
            p.notes,
            _now(),
            p.id,
        ),
    )
    conn.commit()


def get_prestataire(conn: sqlite3.Connection, prestataire_id: int) -> Optional[Prestataire]:
    row = conn.execute(
        "SELECT * FROM prestataires WHERE id = ?", (prestataire_id,)
    ).fetchone()
    return _row_to_prestataire(row) if row else None


def _prestataire_filter_clause(search: str) -> tuple[str, list[Any]]:
    """Clause WHERE (recherche nom/prenom insensible aux accents) pour les prestataires."""
    if not search.strip():
        return "", []
    needle = f"%{slugify(search)}%"
    where = (
        " WHERE ((slug_nom || '_' || slug_prenom) LIKE ? "
        "OR (slug_prenom || '_' || slug_nom) LIKE ?)"
    )
    return where, [needle, needle]


def list_prestataires(
    conn: sqlite3.Connection, search: str = "",
    limit: int | None = None, offset: int = 0,
) -> list[Prestataire]:
    where, params = _prestataire_filter_clause(search)
    sql = f"SELECT * FROM prestataires{where} ORDER BY slug_nom, slug_prenom"
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_prestataire(r) for r in rows]


def count_prestataires(conn: sqlite3.Connection, search: str = "") -> int:
    where, params = _prestataire_filter_clause(search)
    row = conn.execute(
        f"SELECT COUNT(*) AS n FROM prestataires{where}", params
    ).fetchone()
    return int(row["n"])


def find_prestataire_matches(
    conn: sqlite3.Connection, nom: str, prenom: str
) -> list[Prestataire]:
    """Prestataires potentiellement identiques (meme slug nom+prenom) : detection doublon."""
    rows = conn.execute(
        "SELECT * FROM prestataires WHERE slug_nom = ? AND slug_prenom = ?",
        (slugify(nom), slugify(prenom or "")),
    ).fetchall()
    return [_row_to_prestataire(r) for r in rows]


def get_or_create_prestataire(
    conn: sqlite3.Connection, nom: str, prenom: str = "", **extra: Any
) -> tuple[Prestataire, bool]:
    """Renvoie (prestataire, created). Reutilise un prestataire au slug identique s'il existe."""
    existing = find_prestataire_matches(conn, nom, prenom)
    if existing:
        return existing[0], False
    p = Prestataire(id=None, nom=nom, prenom=prenom, **extra)
    return create_prestataire(conn, p), True


# --- Factures importees --------------------------------------------------------

@dataclass
class Facture:
    id: Optional[int]
    prestataire_id: int
    fichier: str
    nom_original: Optional[str] = None
    montant: Optional[float] = None
    libelle: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None


def _row_to_facture(row: sqlite3.Row) -> Facture:
    return Facture(
        id=row["id"],
        prestataire_id=row["prestataire_id"],
        fichier=row["fichier"],
        nom_original=row["nom_original"],
        montant=row["montant"],
        libelle=row["libelle"],
        notes=row["notes"],
        created_at=row["created_at"],
    )


def create_facture(conn: sqlite3.Connection, f: Facture) -> Facture:
    cur = conn.execute(
        """INSERT INTO factures
           (prestataire_id, fichier, nom_original, montant, libelle, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (f.prestataire_id, f.fichier, f.nom_original, f.montant, f.libelle, f.notes),
    )
    conn.commit()
    f.id = cur.lastrowid
    return f


def get_facture(conn: sqlite3.Connection, facture_id: int) -> Optional[Facture]:
    row = conn.execute("SELECT * FROM factures WHERE id = ?", (facture_id,)).fetchone()
    return _row_to_facture(row) if row else None


def list_factures(
    conn: sqlite3.Connection, prestataire_id: int,
    limit: int | None = None, offset: int = 0,
) -> list[Facture]:
    sql = "SELECT * FROM factures WHERE prestataire_id = ? ORDER BY id DESC"
    params: list[Any] = [prestataire_id]
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_facture(r) for r in rows]


def count_factures_for_prestataire(conn: sqlite3.Connection, prestataire_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM factures WHERE prestataire_id = ?", (prestataire_id,)
    ).fetchone()
    return int(row["n"])


def delete_facture(conn: sqlite3.Connection, facture_id: int) -> None:
    """Supprime la ligne facture. La suppression du fichier archive est geree par l'appelant."""
    conn.execute("DELETE FROM factures WHERE id = ?", (facture_id,))
    conn.commit()


# --- Depenses (calque de Paiement, etendu au reglement partiel) ----------------

# Statuts d'une depense (symetrie volontaire avec paiements en_attente/encaisse,
# enrichie d'un etat partiel).
DEPENSE_STATUTS = ("en_attente", "regle_partiellement", "regle")


def statut_depense(montant: float, regle: float) -> str:
    """Statut derive du cumul regle (source unique de verite). A appeler a chaque ecriture."""
    if regle <= 0:
        return "en_attente"
    if regle + 1e-9 < (montant or 0):
        return "regle_partiellement"
    return "regle"


def statut_paiement(montant: float, regle: float) -> str:
    """Statut d'une note derive du cumul regle (source unique de verite). Calque de
    `statut_depense` mais l'etat solde reste 'encaisse' (compat ascendante : tous les
    filtres existants — encaissements, tresorerie, creances — lisent statut='encaisse')."""
    if regle <= 0:
        return "en_attente"
    if regle + 1e-9 < (montant or 0):
        return "regle_partiellement"
    return "encaisse"


@dataclass
class Depense:
    id: Optional[int]
    prestataire_id: int
    facture_id: Optional[int] = None
    montant: float = 0.0
    montant_regle: float = 0.0
    statut: str = "en_attente"
    mode: Optional[str] = None
    motif: Optional[str] = None
    date_echeance: Optional[str] = None
    date_paiement: Optional[str] = None
    libelle: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None

    @property
    def reste(self) -> float:
        return max(0.0, (self.montant or 0) - (self.montant_regle or 0))


def _row_to_depense(row: sqlite3.Row) -> Depense:
    return Depense(
        id=row["id"],
        prestataire_id=row["prestataire_id"],
        facture_id=row["facture_id"],
        montant=row["montant"],
        montant_regle=row["montant_regle"],
        statut=row["statut"],
        mode=row["mode"],
        motif=row["motif"],
        date_echeance=row["date_echeance"],
        date_paiement=row["date_paiement"],
        libelle=row["libelle"],
        notes=row["notes"],
        created_at=row["created_at"],
    )


def create_depense(
    conn: sqlite3.Connection,
    prestataire_id: int,
    montant: float,
    *,
    montant_regle: float = 0.0,
    motif: Optional[str] = None,
    facture_id: Optional[int] = None,
    date_echeance: Optional[str] = None,
    mode: Optional[str] = None,
    libelle: Optional[str] = None,
    notes: Optional[str] = None,
) -> Depense:
    """Cree une depense. `montant` > 0 ; `montant_regle` (avance) borne a [0, montant]."""
    if montant is None or montant <= 0:
        raise ValueError("Le montant d'une depense doit etre strictement superieur a 0.")
    regle = max(0.0, min(float(montant_regle or 0), float(montant)))
    statut = statut_depense(float(montant), regle)
    date_paiement = _now() if regle > 0 else None
    cur = conn.execute(
        """INSERT INTO depenses
           (prestataire_id, facture_id, montant, montant_regle, statut, mode, motif,
            date_echeance, date_paiement, libelle, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (prestataire_id, facture_id, float(montant), regle, statut, mode, motif,
         date_echeance, date_paiement, libelle, notes),
    )
    depense_id = cur.lastrowid
    # Avance saisie a la creation => 1re ligne d'historique (flux de tresorerie).
    if regle > 0:
        conn.execute(
            "INSERT INTO depense_reglements (depense_id, montant, mode, motif, date_reglement) "
            "VALUES (?, ?, ?, ?, ?)",
            (depense_id, regle, mode, motif, date_paiement),
        )
    conn.commit()
    return get_depense(conn, depense_id)  # type: ignore[arg-type, return-value]


def add_depense_reglement(
    conn: sqlite3.Connection,
    depense_id: int,
    versement: float,
    *,
    mode: Optional[str] = None,
    motif: Optional[str] = None,
    when: Optional[str] = None,
) -> Depense:
    """Enregistre un versement (partiel ou solde). Incremente le cumul et derive le statut."""
    dep = get_depense(conn, depense_id)
    if dep is None:
        raise ValueError("Depense introuvable.")
    if versement is None or versement <= 0:
        raise ValueError("Le versement doit etre strictement superieur a 0.")
    if versement > dep.reste + 1e-9:
        raise ValueError("Le versement depasse le reste a payer.")
    nouveau = float(dep.montant_regle or 0) + float(versement)
    statut = statut_depense(float(dep.montant or 0), nouveau)
    when = when or _now()
    conn.execute(
        "UPDATE depenses SET montant_regle = ?, statut = ?, date_paiement = ?, "
        "mode = COALESCE(?, mode), motif = COALESCE(?, motif) WHERE id = ?",
        (nouveau, statut, when, mode, motif, depense_id),
    )
    # Ligne d'historique du versement (datee) : alimente le flux de tresorerie.
    conn.execute(
        "INSERT INTO depense_reglements (depense_id, montant, mode, motif, date_reglement) "
        "VALUES (?, ?, ?, ?, ?)",
        (depense_id, float(versement), mode, motif, when),
    )
    conn.commit()
    return get_depense(conn, depense_id)  # type: ignore[return-value]


def get_depense(conn: sqlite3.Connection, depense_id: int) -> Optional[Depense]:
    row = conn.execute("SELECT * FROM depenses WHERE id = ?", (depense_id,)).fetchone()
    return _row_to_depense(row) if row else None


def list_depenses(
    conn: sqlite3.Connection, prestataire_id: int,
    limit: int | None = None, offset: int = 0,
) -> list[Depense]:
    sql = "SELECT * FROM depenses WHERE prestataire_id = ? ORDER BY id DESC"
    params: list[Any] = [prestataire_id]
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_depense(r) for r in rows]


def count_depenses_for_prestataire(conn: sqlite3.Connection, prestataire_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM depenses WHERE prestataire_id = ?", (prestataire_id,)
    ).fetchone()
    return int(row["n"])


def delete_depense(conn: sqlite3.Connection, depense_id: int) -> None:
    conn.execute("DELETE FROM depenses WHERE id = ?", (depense_id,))
    conn.commit()


def _depense_filter_clause(
    search: str, statut: str, date_from: str = "", date_to: str = "",
) -> tuple[str, list[Any]]:
    """Clause WHERE (et parametres) pour la liste des depenses jointe au prestataire.

    `statut` : en_attente | regle_partiellement | regle | tous. La colonne date du
    filtre periode est contextuelle au statut (calque paiements) : date_paiement pour
    les regles/partiels, date_echeance pour en_attente, sinon created_at.
    """
    clauses: list[str] = []
    params: list[Any] = []
    if statut in DEPENSE_STATUTS:
        clauses.append("d.statut = ?")
        params.append(statut)
    if search.strip():
        needle = f"%{slugify(search)}%"
        clauses.append(
            "((pr.slug_nom || '_' || pr.slug_prenom) LIKE ? "
            "OR (pr.slug_prenom || '_' || pr.slug_nom) LIKE ?)"
        )
        params += [needle, needle]
    date_col = {
        "regle": "d.date_paiement",
        "regle_partiellement": "d.date_paiement",
        "en_attente": "d.date_echeance",
    }.get(statut, "d.created_at")
    if date_from.strip():
        clauses.append(f"date({date_col}) >= ?")
        params.append(date_from.strip())
    if date_to.strip():
        clauses.append(f"date({date_col}) <= ?")
        params.append(date_to.strip())
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def list_depenses_filtered(
    conn: sqlite3.Connection,
    search: str = "",
    statut: str = "en_attente",
    limit: int | None = None,
    offset: int = 0,
    date_from: str = "",
    date_to: str = "",
) -> list[tuple[Depense, Prestataire]]:
    """Liste paginee des depenses jointes a leur prestataire, filtree par statut/recherche."""
    where, params = _depense_filter_clause(search, statut, date_from, date_to)
    sql = (
        "SELECT d.*, pr.id AS pr_id, pr.nom, pr.prenom, pr.email, pr.telephone, "
        "pr.adresse, pr.notes AS pr_notes "
        "FROM depenses d JOIN prestataires pr ON pr.id = d.prestataire_id"
        f"{where} "
        "ORDER BY d.date_echeance IS NULL, d.date_echeance, d.id DESC"
    )
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    rows = conn.execute(sql, params).fetchall()
    out: list[tuple[Depense, Prestataire]] = []
    for r in rows:
        depense = _row_to_depense(r)
        prestataire = Prestataire(
            id=r["pr_id"], nom=r["nom"], prenom=r["prenom"], email=r["email"],
            telephone=r["telephone"], adresse=r["adresse"], notes=r["pr_notes"],
        )
        out.append((depense, prestataire))
    return out


def count_depenses(
    conn: sqlite3.Connection,
    search: str = "",
    statut: str = "en_attente",
    date_from: str = "",
    date_to: str = "",
) -> int:
    where, params = _depense_filter_clause(search, statut, date_from, date_to)
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM depenses d "
        f"JOIN prestataires pr ON pr.id = d.prestataire_id{where}",
        params,
    ).fetchone()
    return int(row["n"])


def total_depenses(
    conn: sqlite3.Connection,
    search: str = "",
    statut: str = "tous",
    date_from: str = "",
    date_to: str = "",
) -> tuple[float, float, float]:
    """Renvoie (total_du, total_regle, reste_a_payer) sur le filtre (pour KPI / recap)."""
    where, params = _depense_filter_clause(search, statut, date_from, date_to)
    row = conn.execute(
        "SELECT COALESCE(SUM(d.montant), 0) AS du, "
        "COALESCE(SUM(d.montant_regle), 0) AS regle, "
        "COALESCE(SUM(d.montant - d.montant_regle), 0) AS reste "
        "FROM depenses d "
        f"JOIN prestataires pr ON pr.id = d.prestataire_id{where}",
        params,
    ).fetchone()
    return float(row["du"] or 0), float(row["regle"] or 0), float(row["reste"] or 0)


# --- Historique des reglements (v7) : flux de tresorerie par date de transaction ----

@dataclass
class Reglement:
    id: Optional[int]
    depense_id: int
    montant: float
    mode: Optional[str] = None
    motif: Optional[str] = None
    date_reglement: Optional[str] = None
    created_at: Optional[str] = None


def _row_to_reglement(row: sqlite3.Row) -> Reglement:
    return Reglement(
        id=row["id"],
        depense_id=row["depense_id"],
        montant=row["montant"],
        mode=row["mode"],
        motif=row["motif"],
        date_reglement=row["date_reglement"],
        created_at=row["created_at"],
    )


def list_reglements(conn: sqlite3.Connection, depense_id: int) -> list[Reglement]:
    """Versements d'une depense (du plus recent au plus ancien)."""
    rows = conn.execute(
        "SELECT * FROM depense_reglements WHERE depense_id = ? "
        "ORDER BY date(date_reglement) DESC, id DESC",
        (depense_id,),
    ).fetchall()
    return [_row_to_reglement(r) for r in rows]


def total_regle_periode(
    conn: sqlite3.Connection, date_from: str = "", date_to: str = ""
) -> float:
    """Somme des montants REELLEMENT verses sur la periode (par `date_reglement`).

    Exact pour les reglements partiels (1 ligne par versement), contrairement au cumul
    `depenses.montant_regle`. C'est la sortie de tresorerie de la periode.
    """
    clauses: list[str] = []
    params: list[Any] = []
    if date_from.strip():
        clauses.append("date(date_reglement) >= ?")
        params.append(date_from.strip())
    if date_to.strip():
        clauses.append("date(date_reglement) <= ?")
        params.append(date_to.strip())
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    row = conn.execute(
        f"SELECT COALESCE(SUM(montant), 0) AS total FROM depense_reglements{where}", params
    ).fetchone()
    return float(row["total"] or 0)


# --- Plans de traitement & actes realises (prestations) -----------------------
# Cote PATIENT, calque du sous-systeme `depenses` cote fournisseur : un acte
# (`prestations`) porte a la fois le DU (`montant`) et le PAIEMENT (`montant_regle`
# cumul, `statut`, `reste` derive), avec un historique de versements datees
# (`prestation_reglements`). Le plan n'est qu'un regroupement nomme, SANS statut.
# Le prix est un SNAPSHOT recopie depuis le referentiel d'actes (D3). Voir
# openspec/changes/plans-de-traitement.

# Sentinelle pour distinguer, dans list_prestations, "tous les actes du patient"
# (parametre absent) de "actes isoles" (plan_id=None -> plan_id IS NULL).
_UNSET: Any = object()


def normalize_dents(raw: Optional[str]) -> str:
    """Normalise une saisie de dents (FDI) en chaine « 26, 27 ».

    Decoupe sur virgules / points-virgules / sauts de ligne (PAS sur l'espace, pour
    tolerer une saisie libre type « 26 (MOD) »), retire les vides et deduplique en
    conservant l'ordre. Validation FDI volontairement NON bloquante (D10). Renvoie
    "" si rien d'exploitable.
    """
    if not raw:
        return ""
    parts: list[str] = []
    for chunk in re.split(r"[,;\n]+", raw):
        token = chunk.strip()
        if token and token not in parts:
            parts.append(token)
    return ", ".join(parts)


# --- Notation FDI (odontogramme) ---------------------------------------------
#
# Quadrants FDI (vue « face au patient ») :
#   permanentes : 1 = maxillaire droit, 2 = maxillaire gauche,
#                 3 = mandibulaire gauche, 4 = mandibulaire droit ;
#   temporaires : 5/6/7/8 selon le meme decoupage (denture de lait).
# Dans chaque quadrant la dent est numerotee de 1 (incisive centrale, pres de la
# ligne mediane) vers l'arriere (8 pour les permanentes, 5 pour les temporaires).

# Denture adulte : dents permanentes 11-18, 21-28, 31-38, 41-48.
DENTS_PERMANENTES: dict[int, list[str]] = {
    q: [f"{q}{d}" for d in range(1, 9)] for q in (1, 2, 3, 4)
}

# Denture enfant : dents temporaires 51-55, 61-65, 71-75, 81-85.
DENTS_TEMPORAIRES: dict[int, list[str]] = {
    q: [f"{q}{d}" for d in range(1, 6)] for q in (5, 6, 7, 8)
}

# Ensemble plat de tous les numeros FDI valides (permanentes + temporaires).
_FDI_VALIDES: frozenset[str] = frozenset(
    n for quadrants in (DENTS_PERMANENTES, DENTS_TEMPORAIRES)
    for nums in quadrants.values() for n in nums
)


def is_fdi_valide(num: Optional[str]) -> bool:
    """Vrai si `num` est un numero de dent FDI valide (permanente ou temporaire).

    Volontairement strict (sert le surlignage de l'odontogramme) : une saisie
    libre non FDI renvoie False et n'est simplement pas reflechie sur le schema,
    sans bloquer la saisie (cf. `normalize_dents`).
    """
    return (num or "").strip() in _FDI_VALIDES


def fdi_quadrant(num: Optional[str]) -> Optional[int]:
    """Quadrant FDI (1..8) d'un numero de dent valide, sinon None."""
    token = (num or "").strip()
    return int(token[0]) if is_fdi_valide(token) else None


def denture_par_defaut(date_naissance: Optional[str]) -> str:
    """Denture a afficher par defaut dans l'odontogramme.

    Renvoie « enfant » pour un jeune patient (age < 13 ans), « adulte » sinon —
    y compris quand la date de naissance est absente ou illisible (defaut adulte).
    `date_naissance` est attendue en ISO « AAAA-MM-JJ » (format de stockage).
    """
    iso = (date_naissance or "").strip()
    if not iso:
        return "adulte"
    try:
        ddn = datetime.strptime(iso[:10], "%Y-%m-%d").date()
    except ValueError:
        return "adulte"
    today = date.today()
    age = today.year - ddn.year - ((today.month, today.day) < (ddn.month, ddn.day))
    return "enfant" if age < 13 else "adulte"


@dataclass
class PlanTraitement:
    id: Optional[int]
    patient_id: int
    titre: str
    notes: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class Prestation:
    id: Optional[int]
    patient_id: int
    plan_id: Optional[int] = None
    acte_id: Optional[int] = None
    libelle: str = ""
    montant: float = 0.0
    montant_regle: float = 0.0
    statut: str = "en_attente"
    date_acte: Optional[str] = None
    dents: Optional[str] = None
    note: Optional[str] = None
    sort_order: int = 0
    created_at: Optional[str] = None

    @property
    def reste(self) -> float:
        return max(0.0, (self.montant or 0) - (self.montant_regle or 0))

    @property
    def facturable(self) -> bool:
        """Un acte a montant nul (controle, geste gratuit) est NON facturable (D5)."""
        return (self.montant or 0) > 0


@dataclass
class PrestationReglement:
    id: Optional[int]
    prestation_id: int
    montant: float
    mode: Optional[str] = None
    date_reglement: Optional[str] = None
    created_at: Optional[str] = None


def _row_to_plan(row: sqlite3.Row) -> PlanTraitement:
    return PlanTraitement(
        id=row["id"],
        patient_id=row["patient_id"],
        titre=row["titre"],
        notes=row["notes"],
        created_at=row["created_at"],
    )


def _row_to_prestation(row: sqlite3.Row) -> Prestation:
    return Prestation(
        id=row["id"],
        patient_id=row["patient_id"],
        plan_id=row["plan_id"],
        acte_id=row["acte_id"],
        libelle=row["libelle"],
        montant=row["montant"],
        montant_regle=row["montant_regle"],
        statut=row["statut"],
        date_acte=row["date_acte"],
        dents=row["dents"],
        note=row["note"],
        sort_order=row["sort_order"],
        created_at=row["created_at"],
    )


def _row_to_prestation_reglement(row: sqlite3.Row) -> PrestationReglement:
    return PrestationReglement(
        id=row["id"],
        prestation_id=row["prestation_id"],
        montant=row["montant"],
        mode=row["mode"],
        date_reglement=row["date_reglement"],
        created_at=row["created_at"],
    )


# --- CRUD plans ---------------------------------------------------------------

def create_plan(
    conn: sqlite3.Connection, patient_id: int, titre: str,
    notes: Optional[str] = None,
) -> PlanTraitement:
    """Cree un plan (regroupement nomme). Titre obligatoire ; aucun statut (D4)."""
    titre = (titre or "").strip()
    if not titre:
        raise ValueError("Le titre d'un plan de traitement est obligatoire.")
    cur = conn.execute(
        "INSERT INTO plans_traitement (patient_id, titre, notes) VALUES (?, ?, ?)",
        (patient_id, titre, (notes or None)),
    )
    conn.commit()
    return get_plan(conn, cur.lastrowid)  # type: ignore[arg-type, return-value]


def update_plan(
    conn: sqlite3.Connection, plan_id: int, titre: str,
    notes: Optional[str] = None,
) -> None:
    titre = (titre or "").strip()
    if not titre:
        raise ValueError("Le titre d'un plan de traitement est obligatoire.")
    conn.execute(
        "UPDATE plans_traitement SET titre = ?, notes = ? WHERE id = ?",
        (titre, (notes or None), plan_id),
    )
    conn.commit()


def list_plans(conn: sqlite3.Connection, patient_id: int) -> list[PlanTraitement]:
    rows = conn.execute(
        "SELECT * FROM plans_traitement WHERE patient_id = ? ORDER BY id DESC",
        (patient_id,),
    ).fetchall()
    return [_row_to_plan(r) for r in rows]


def get_plan(conn: sqlite3.Connection, plan_id: int) -> Optional[PlanTraitement]:
    row = conn.execute(
        "SELECT * FROM plans_traitement WHERE id = ?", (plan_id,)
    ).fetchone()
    return _row_to_plan(row) if row else None


def delete_plan(conn: sqlite3.Connection, plan_id: int) -> None:
    """Supprime un plan. Ses actes sont DETACHES (plan_id -> NULL via ON DELETE SET
    NULL) et deviennent des actes isoles : aucun reglement n'est jamais perdu (D8)."""
    conn.execute("DELETE FROM plans_traitement WHERE id = ?", (plan_id,))
    conn.commit()


# --- CRUD prestations (actes realises) ----------------------------------------

def create_prestation(
    conn: sqlite3.Connection,
    patient_id: int,
    libelle: str,
    montant: float,
    *,
    plan_id: Optional[int] = None,
    acte_id: Optional[int] = None,
    date_acte: Optional[str] = None,
    dents: Optional[str] = None,
    note: Optional[str] = None,
    sort_order: int = 0,
) -> Prestation:
    """Cree un acte realise. `libelle`/`montant` sont un SNAPSHOT fourni par
    l'appelant (recopie depuis le referentiel, modifiable). `montant >= 0` (un acte
    a 0 est un controle non facturable, D5). Pas de creation de paiement (D13)."""
    libelle = (libelle or "").strip()
    if not libelle:
        raise ValueError("Le libelle d'un acte est obligatoire.")
    if montant is None or montant < 0:
        raise ValueError("Le montant d'un acte doit etre positif ou nul.")
    cur = conn.execute(
        """INSERT INTO prestations
           (patient_id, plan_id, acte_id, libelle, montant, montant_regle, statut,
            date_acte, dents, note, sort_order)
           VALUES (?, ?, ?, ?, ?, 0, 'en_attente', ?, ?, ?, ?)""",
        (patient_id, plan_id, acte_id, libelle, float(montant), date_acte,
         (normalize_dents(dents) or None), (note or None), sort_order or 0),
    )
    conn.commit()
    return get_prestation(conn, cur.lastrowid)  # type: ignore[arg-type, return-value]


def update_prestation(
    conn: sqlite3.Connection,
    prestation_id: int,
    *,
    libelle: str,
    montant: float,
    plan_id: Optional[int] = None,
    acte_id: Optional[int] = None,
    date_acte: Optional[str] = None,
    dents: Optional[str] = None,
    note: Optional[str] = None,
) -> None:
    """Met a jour les champs editables d'un acte. Le cumul regle n'est pas touche ;
    le statut est recalcule depuis le nouveau montant. Refuse un montant inferieur
    au deja regle (on ne peut pas facturer moins que ce qui est encaisse)."""
    pres = get_prestation(conn, prestation_id)
    if pres is None:
        raise ValueError("Acte introuvable.")
    libelle = (libelle or "").strip()
    if not libelle:
        raise ValueError("Le libelle d'un acte est obligatoire.")
    if montant is None or montant < 0:
        raise ValueError("Le montant d'un acte doit etre positif ou nul.")
    if float(montant) + 1e-9 < float(pres.montant_regle or 0):
        raise ValueError("Le montant ne peut pas etre inferieur au deja regle.")
    statut = statut_depense(float(montant), float(pres.montant_regle or 0))
    conn.execute(
        """UPDATE prestations SET libelle = ?, montant = ?, statut = ?, plan_id = ?,
             acte_id = ?, date_acte = ?, dents = ?, note = ? WHERE id = ?""",
        (libelle, float(montant), statut, plan_id, acte_id, date_acte,
         (normalize_dents(dents) or None), (note or None), prestation_id),
    )
    conn.commit()


def list_prestations(
    conn: sqlite3.Connection, patient_id: int, plan_id: Any = _UNSET,
) -> list[Prestation]:
    """Actes d'un patient. `plan_id` absent => tous ; `plan_id=None` => actes isoles
    (plan_id IS NULL) ; `plan_id=<id>` => actes du plan. Tri sort_order, id."""
    sql = "SELECT * FROM prestations WHERE patient_id = ?"
    params: list[Any] = [patient_id]
    if plan_id is None:
        sql += " AND plan_id IS NULL"
    elif plan_id is not _UNSET:
        sql += " AND plan_id = ?"
        params.append(plan_id)
    sql += " ORDER BY sort_order, id"
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_prestation(r) for r in rows]


def get_prestation(conn: sqlite3.Connection, prestation_id: int) -> Optional[Prestation]:
    row = conn.execute(
        "SELECT * FROM prestations WHERE id = ?", (prestation_id,)
    ).fetchone()
    return _row_to_prestation(row) if row else None


def prestation_has_reglements(conn: sqlite3.Connection, prestation_id: int) -> bool:
    """Vrai si l'acte porte au moins un versement (garde de suppression, D8)."""
    row = conn.execute(
        "SELECT 1 FROM prestation_reglements WHERE prestation_id = ? LIMIT 1",
        (prestation_id,),
    ).fetchone()
    return row is not None


def delete_prestation(conn: sqlite3.Connection, prestation_id: int) -> None:
    """Supprime un acte. REFUSE si des reglements existent (preserve la trace
    financiere, D8) : il faut d'abord le solder/annuler explicitement."""
    if prestation_has_reglements(conn, prestation_id):
        raise ValueError("Impossible de supprimer un acte portant des reglements.")
    conn.execute("DELETE FROM prestations WHERE id = ?", (prestation_id,))
    conn.commit()


def add_prestation_reglement(
    conn: sqlite3.Connection,
    prestation_id: int,
    montant: float,
    *,
    mode: Optional[str] = None,
    date_reglement: Optional[str] = None,
) -> Prestation:
    """Enregistre un versement (partiel ou solde) sur un acte. Calque de
    `add_depense_reglement` : incremente le cumul, derive le statut, historise le
    versement date. Refuse un montant <= 0 ou superieur au reste a payer."""
    pres = get_prestation(conn, prestation_id)
    if pres is None:
        raise ValueError("Acte introuvable.")
    if montant is None or montant <= 0:
        raise ValueError("Le versement doit etre strictement superieur a 0.")
    if montant > pres.reste + 1e-9:
        raise ValueError("Le versement depasse le reste a payer.")
    nouveau = float(pres.montant_regle or 0) + float(montant)
    statut = statut_depense(float(pres.montant or 0), nouveau)
    when = date_reglement or _now()
    conn.execute(
        "UPDATE prestations SET montant_regle = ?, statut = ? WHERE id = ?",
        (nouveau, statut, prestation_id),
    )
    conn.execute(
        "INSERT INTO prestation_reglements (prestation_id, montant, mode, date_reglement) "
        "VALUES (?, ?, ?, ?)",
        (prestation_id, float(montant), mode, when),
    )
    conn.commit()
    return get_prestation(conn, prestation_id)  # type: ignore[return-value]


def list_prestation_reglements(
    conn: sqlite3.Connection, prestation_id: int
) -> list[PrestationReglement]:
    """Versements d'un acte (du plus recent au plus ancien)."""
    rows = conn.execute(
        "SELECT * FROM prestation_reglements WHERE prestation_id = ? "
        "ORDER BY date(date_reglement) DESC, id DESC",
        (prestation_id,),
    ).fetchall()
    return [_row_to_prestation_reglement(r) for r in rows]


def plan_totaux(
    conn: sqlite3.Connection, plan_id: int
) -> tuple[float, float, float]:
    """(du, encaisse, reste) d'un plan. Les actes a montant=0 sont naturellement
    neutres (montant et montant_regle nuls)."""
    row = conn.execute(
        "SELECT COALESCE(SUM(montant), 0) AS du, "
        "COALESCE(SUM(montant_regle), 0) AS encaisse, "
        "COALESCE(SUM(montant - montant_regle), 0) AS reste "
        "FROM prestations WHERE plan_id = ?",
        (plan_id,),
    ).fetchone()
    return float(row["du"] or 0), float(row["encaisse"] or 0), float(row["reste"] or 0)


def list_prestations_a_regler(
    conn: sqlite3.Connection, patient_id: int
) -> list[Prestation]:
    """Actes FACTURABLES non soldes (montant>0 et reste>0) d'un patient, pour le
    recap « Regler ». Les actes a montant=0 (controles) sont exclus (D5)."""
    rows = conn.execute(
        "SELECT * FROM prestations WHERE patient_id = ? AND montant > 0 "
        "AND (montant - montant_regle) > 1e-9 ORDER BY sort_order, id",
        (patient_id,),
    ).fetchall()
    return [_row_to_prestation(r) for r in rows]


# --- Vue Finances unifiee : creances (paiements en attente + actes au reste) ---
# D7 : l'ecran Finances agrege, AU MEME ENDROIT, les paiements en attente (creance
# de note) et les actes au reste positif (creance d'acte). Chaque ligne garde sa
# nature ('note' | 'acte') et son action propre (encaisser / regler).

@dataclass
class Creance:
    nature: str            # 'note' (paiement) | 'acte' (prestation)
    source_id: int         # id du paiement ou de la prestation
    patient: "Patient"
    libelle: str
    montant: float         # montant total de la creance
    reste: float           # reste a recouvrer
    date: Optional[str]    # echeance (note) ou date_acte (acte) — cle de tri
    statut: str            # statut de la source


def _creance_branch_clause(
    search: str, date_from: str, date_to: str, date_col: str,
) -> tuple[list[str], list[Any]]:
    """Clauses additionnelles (recherche patient + periode) d'une branche d'union.
    `date_col` est la colonne de date contextuelle de la branche (echeance / acte)."""
    clauses: list[str] = []
    params: list[Any] = []
    if search.strip():
        needle = f"%{slugify(search)}%"
        clauses.append(
            "((pt.slug_nom || '_' || pt.slug_prenom) LIKE ? "
            "OR (pt.slug_prenom || '_' || pt.slug_nom) LIKE ?)"
        )
        params += [needle, needle]
    if date_from.strip():
        clauses.append(f"date({date_col}) >= ?")
        params.append(date_from.strip())
    if date_to.strip():
        clauses.append(f"date({date_col}) <= ?")
        params.append(date_to.strip())
    return clauses, params


def _creances_union(
    search: str, date_from: str, date_to: str,
) -> tuple[str, list[Any]]:
    """SQL (et parametres) de l'UNION des creances : paiements en attente + actes au
    reste positif, normalises en colonnes communes. Sans ORDER BY / LIMIT (ajoutes
    par l'appelant)."""
    note_clauses, note_params = _creance_branch_clause(
        search, date_from, date_to, "pa.date_echeance"
    )
    acte_clauses, acte_params = _creance_branch_clause(
        search, date_from, date_to, "pr.date_acte"
    )
    note_where = " AND ".join(
        ["pa.statut IN ('en_attente', 'regle_partiellement')",
         "(pa.montant - pa.montant_regle) > 1e-9"] + note_clauses
    )
    acte_where = " AND ".join(
        ["pr.montant > 0", "(pr.montant - pr.montant_regle) > 1e-9"] + acte_clauses
    )
    sql = (
        "SELECT 'note' AS nature, pa.id AS source_id, "
        "pt.id AS p_id, pt.nom, pt.prenom, pt.date_naissance, pt.email, "
        "pt.telephone, pt.adresse, pt.notes AS p_notes, "
        "COALESCE(NULLIF(d.acte, ''), NULLIF(pa.notes, ''), 'Note d''honoraires') AS libelle, "
        "pa.montant AS montant, (pa.montant - pa.montant_regle) AS reste, "
        "pa.date_echeance AS date_ref, pa.statut AS statut "
        "FROM paiements pa JOIN patients pt ON pt.id = pa.patient_id "
        "LEFT JOIN documents d ON d.id = pa.document_id "
        f"WHERE {note_where} "
        "UNION ALL "
        "SELECT 'acte' AS nature, pr.id AS source_id, "
        "pt.id AS p_id, pt.nom, pt.prenom, pt.date_naissance, pt.email, "
        "pt.telephone, pt.adresse, pt.notes AS p_notes, "
        "pr.libelle AS libelle, "
        "pr.montant AS montant, (pr.montant - pr.montant_regle) AS reste, "
        "pr.date_acte AS date_ref, pr.statut AS statut "
        "FROM prestations pr JOIN patients pt ON pt.id = pr.patient_id "
        f"WHERE {acte_where}"
    )
    return sql, note_params + acte_params


def list_creances(
    conn: sqlite3.Connection,
    search: str = "",
    date_from: str = "",
    date_to: str = "",
    limit: int | None = None,
    offset: int = 0,
) -> list[Creance]:
    """Creances a recouvrer (notes en attente + actes au reste positif), triees par
    echeance/date (les plus urgentes d'abord, sans date en dernier)."""
    union, params = _creances_union(search, date_from, date_to)
    sql = (
        f"SELECT * FROM ({union}) "
        "ORDER BY date_ref IS NULL, date_ref, nature, source_id DESC"
    )
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params = params + [limit, offset]
    rows = conn.execute(sql, params).fetchall()
    out: list[Creance] = []
    for r in rows:
        patient = Patient(
            id=r["p_id"], nom=r["nom"], prenom=r["prenom"],
            date_naissance=r["date_naissance"], email=r["email"],
            telephone=r["telephone"], adresse=r["adresse"], notes=r["p_notes"],
        )
        out.append(Creance(
            nature=r["nature"], source_id=r["source_id"], patient=patient,
            libelle=r["libelle"], montant=float(r["montant"] or 0),
            reste=float(r["reste"] or 0), date=r["date_ref"], statut=r["statut"],
        ))
    return out


def count_creances(
    conn: sqlite3.Connection, search: str = "", date_from: str = "", date_to: str = "",
) -> int:
    union, params = _creances_union(search, date_from, date_to)
    row = conn.execute(f"SELECT COUNT(*) AS n FROM ({union})", params).fetchone()
    return int(row["n"])


def total_creances(
    conn: sqlite3.Connection, search: str = "", date_from: str = "", date_to: str = "",
) -> float:
    """Total a recouvrer = somme des restes des deux sources (notes + actes)."""
    union, params = _creances_union(search, date_from, date_to)
    row = conn.execute(
        f"SELECT COALESCE(SUM(reste), 0) AS total FROM ({union})", params
    ).fetchone()
    return float(row["total"] or 0)


def total_encaisse(
    conn: sqlite3.Connection, date_from: str = "", date_to: str = "",
) -> float:
    """Tresorerie REELLEMENT encaissee sur la periode : versements de notes
    (paiement_reglements) + reglements d'actes (prestation_reglements), tous deux par
    date_reglement. Agrege les DEUX sources pour les totaux « encaisse » de Finances et
    du tableau de bord (D7)."""
    clauses_r: list[str] = []
    params_r: list[Any] = []
    if date_from.strip():
        clauses_r.append("date(date_reglement) >= ?")
        params_r.append(date_from.strip())
    if date_to.strip():
        clauses_r.append("date(date_reglement) <= ?")
        params_r.append(date_to.strip())
    where_r = (" WHERE " + " AND ".join(clauses_r)) if clauses_r else ""
    row_p = conn.execute(
        f"SELECT COALESCE(SUM(montant), 0) AS t FROM paiement_reglements{where_r}",
        list(params_r),
    ).fetchone()
    row_r = conn.execute(
        f"SELECT COALESCE(SUM(montant), 0) AS t FROM prestation_reglements{where_r}",
        list(params_r),
    ).fetchone()
    return float(row_p["t"] or 0) + float(row_r["t"] or 0)


# --- Reglement global en cascade (D9 revise) ----------------------------------
# Un versement unique est REPARTI automatiquement sur les creances du patient, du
# PLUS ANCIEN au plus recent : d'abord les actes (paiement partiel via
# prestation_reglements), puis (option) les notes (paiement partiel via
# paiement_reglements). Le reliquat non affectable est renvoye a l'appelant.

def creances_patient(
    conn: sqlite3.Connection, patient_id: int, include_notes: bool = True,
) -> list[Creance]:
    """Creances non soldees d'un patient, ORDONNEES pour la cascade (du plus ancien
    au plus recent) : actes facturables au reste positif d'abord (par date d'acte),
    puis, en option, les notes en attente (par echeance). Sert l'apercu et le total
    du dialogue « Regler »."""
    out: list[Creance] = []
    p = get_patient(conn, patient_id)
    if p is None:
        return out
    acts = conn.execute(
        "SELECT * FROM prestations WHERE patient_id = ? AND montant > 0 "
        "AND (montant - montant_regle) > 1e-9 "
        "ORDER BY (date_acte IS NULL), date(date_acte), id",
        (patient_id,),
    ).fetchall()
    for r in acts:
        pres = _row_to_prestation(r)
        out.append(Creance(
            nature="acte", source_id=pres.id, patient=p, libelle=pres.libelle,
            montant=float(pres.montant or 0), reste=pres.reste,
            date=pres.date_acte, statut=pres.statut))
    if include_notes:
        notes = conn.execute(
            "SELECT * FROM paiements WHERE patient_id = ? "
            "AND statut IN ('en_attente', 'regle_partiellement') "
            "AND (montant - montant_regle) > 1e-9 "
            "ORDER BY (date_echeance IS NULL), date(date_echeance), id",
            (patient_id,),
        ).fetchall()
        for r in notes:
            pa = _row_to_paiement(r)
            out.append(Creance(
                nature="note", source_id=pa.id, patient=p,
                libelle=(pa.notes or "Note d'honoraires"),
                montant=float(pa.montant or 0), reste=pa.reste,
                date=pa.date_echeance, statut=pa.statut))
    return out


def regler_creances(
    conn: sqlite3.Connection,
    patient_id: int,
    montant: float,
    *,
    mode: Optional[str] = None,
    date_reglement: Optional[str] = None,
    include_notes: bool = True,
) -> dict:
    """Repartit `montant` sur les creances du patient, du plus ancien au plus recent
    (D9 revise) : actes ET notes en paiement PARTIEL (prestation_reglements /
    paiement_reglements). Chaque creance recoit min(reliquat, reste) ; une note peut
    donc etre soldee partiellement, comme un acte.

    Renvoie {alloue, reste, lignes:[(nature, source_id, libelle, montant)]} ; `reste`
    est le reliquat NON affecte (montant superieur aux creances solvables)."""
    if montant is None or montant <= 0:
        raise ValueError("Le montant a regler doit etre strictement superieur a 0.")
    when = date_reglement or _now()
    remaining = float(montant)
    lignes: list[tuple] = []
    for c in creances_patient(conn, patient_id, include_notes=include_notes):
        if remaining <= 1e-9:
            break
        pay = min(remaining, c.reste)
        if pay <= 1e-9:
            continue
        if c.nature == "acte":
            add_prestation_reglement(conn, c.source_id, pay, mode=mode,
                                     date_reglement=when)
        else:  # note : reglement partiel comme un acte
            add_paiement_reglement(conn, c.source_id, pay, mode=mode,
                                   date_reglement=when)
        remaining -= pay
        lignes.append((c.nature, c.source_id, c.libelle, pay))
    return {"alloue": float(montant) - remaining, "reste": max(0.0, remaining),
            "lignes": lignes}


# --- Historique unifie des encaissements d'un patient (fiche) -----------------
# Bloc « Reglements » de la fiche : ce qui a ete REELLEMENT encaisse, actes et notes
# confondus, synchronise avec les lignes d'actes (chaque versement d'acte y apparait).

@dataclass
class Encaissement:
    nature: str            # 'acte' | 'note'
    source_id: int         # prestation_id ou paiement id
    libelle: str
    montant: float
    mode: Optional[str]
    date: Optional[str]


def list_encaissements_patient(
    conn: sqlite3.Connection, patient_id: int,
    limit: int | None = None, offset: int = 0,
) -> list[Encaissement]:
    """Encaissements d'un patient (recents d'abord) : versements d'actes
    (prestation_reglements) + versements de notes (paiement_reglements). Historique
    unifie, 1 ligne par versement (partiel ou solde)."""
    sql = (
        "SELECT 'acte' AS nature, pr.id AS source_id, pr.libelle AS libelle, "
        "reg.montant AS montant, reg.mode AS mode, reg.date_reglement AS date_ref "
        "FROM prestation_reglements reg JOIN prestations pr ON pr.id = reg.prestation_id "
        "WHERE pr.patient_id = ? "
        "UNION ALL "
        "SELECT 'note' AS nature, pa.id AS source_id, "
        "COALESCE(NULLIF(pa.notes, ''), 'Note d''honoraires') AS libelle, "
        "reg.montant AS montant, reg.mode AS mode, reg.date_reglement AS date_ref "
        "FROM paiement_reglements reg JOIN paiements pa ON pa.id = reg.paiement_id "
        "WHERE pa.patient_id = ? "
    )
    sql = (f"SELECT * FROM ({sql}) "
           "ORDER BY date_ref IS NULL, date(date_ref) DESC, source_id DESC")
    params: list[Any] = [patient_id, patient_id]
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    rows = conn.execute(sql, params).fetchall()
    return [Encaissement(
        nature=r["nature"], source_id=r["source_id"], libelle=r["libelle"],
        montant=float(r["montant"] or 0), mode=r["mode"], date=r["date_ref"],
    ) for r in rows]


def count_encaissements_patient(conn: sqlite3.Connection, patient_id: int) -> int:
    row = conn.execute(
        "SELECT (SELECT COUNT(*) FROM prestation_reglements reg "
        "        JOIN prestations pr ON pr.id = reg.prestation_id "
        "        WHERE pr.patient_id = ?) "
        "     + (SELECT COUNT(*) FROM paiement_reglements reg "
        "        JOIN paiements pa ON pa.id = reg.paiement_id "
        "        WHERE pa.patient_id = ?) AS n",
        (patient_id, patient_id),
    ).fetchone()
    return int(row["n"])


def solde_patient(
    conn: sqlite3.Connection, patient_id: int, include_notes: bool = True,
) -> tuple[float, float, float]:
    """(du, encaisse, reste) consolides d'un patient sur les actes (+ notes en
    option) : du = total facture, encaisse = cumul regle + notes encaissees,
    reste = du - encaisse (actes au reste + notes en attente)."""
    row = conn.execute(
        "SELECT COALESCE(SUM(montant), 0) AS du, "
        "COALESCE(SUM(montant_regle), 0) AS enc FROM prestations WHERE patient_id = ?",
        (patient_id,),
    ).fetchone()
    du = float(row["du"] or 0)
    enc = float(row["enc"] or 0)
    if include_notes:
        rowp = conn.execute(
            "SELECT COALESCE(SUM(montant), 0) AS du, "
            "COALESCE(SUM(montant_regle), 0) AS enc "
            "FROM paiements WHERE patient_id = ?",
            (patient_id,),
        ).fetchone()
        du += float(rowp["du"] or 0)
        enc += float(rowp["enc"] or 0)
    return du, enc, max(0.0, du - enc)
