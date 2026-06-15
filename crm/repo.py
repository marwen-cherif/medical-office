"""Couche d'acces aux donnees (patients, documents, paiements).

Expose des dataclasses simples et des fonctions CRUD au-dessus de sqlite3.
"""

from __future__ import annotations

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
    statut: str = "en_attente"  # en_attente | encaisse
    mode: Optional[str] = None
    date_echeance: Optional[str] = None
    date_encaissement: Optional[str] = None
    notes: Optional[str] = None


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


def update_patient(conn: sqlite3.Connection, p: Patient) -> None:
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
            "id IN (SELECT patient_id FROM paiements WHERE statut = 'en_attente')"
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
    )


def create_document(conn: sqlite3.Connection, d: Document) -> Document:
    cur = conn.execute(
        """INSERT INTO documents
           (patient_id, type, template, acte, montant, acte_date, file_path,
            output_format, statut, date_generation, date_envoi, email,
            mailjet_message_id, mailjet_status, date_refresh_status, message_erreur,
            variables)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            d.patient_id, d.type, d.template, d.acte, d.montant, d.acte_date,
            d.file_path, d.output_format, d.statut, d.date_generation, d.date_envoi,
            d.email, d.mailjet_message_id, d.mailjet_status, d.date_refresh_status,
            d.message_erreur, d.variables,
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
             variables=?, mailjet_opened_at=?, mailjet_clicked_at=?
           WHERE id=?""",
        (
            d.type, d.template, d.acte, d.montant, d.acte_date, d.file_path,
            d.output_format, d.statut, d.date_generation, d.date_envoi, d.email,
            d.mailjet_message_id, d.mailjet_status, d.date_refresh_status,
            d.message_erreur, d.variables, d.mailjet_opened_at, d.mailjet_clicked_at,
            d.id,
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
        statut=row["statut"],
        mode=row["mode"],
        date_echeance=row["date_echeance"],
        date_encaissement=row["date_encaissement"],
        notes=row["notes"],
    )


def create_paiement(conn: sqlite3.Connection, p: Paiement) -> Paiement:
    # Regle metier : un paiement porte toujours un montant strictement positif.
    if p.montant is None or p.montant <= 0:
        raise ValueError("Le montant d'un paiement doit être strictement supérieur à 0.")
    cur = conn.execute(
        """INSERT INTO paiements
           (patient_id, document_id, montant, statut, mode, date_echeance,
            date_encaissement, notes)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            p.patient_id, p.document_id, p.montant, p.statut, p.mode,
            p.date_echeance, p.date_encaissement, p.notes,
        ),
    )
    conn.commit()
    p.id = cur.lastrowid
    return p


def mark_paiement_encaisse(
    conn: sqlite3.Connection, paiement_id: int, when: Optional[str] = None,
    mode: Optional[str] = None,
) -> None:
    """Marque un paiement encaisse. `mode` (especes/cheque/virement), s'il est
    fourni, est enregistre pour la tracabilite ; sinon le mode existant est garde.
    """
    conn.execute(
        "UPDATE paiements SET statut='encaisse', date_encaissement=?, "
        "mode=COALESCE(?, mode) WHERE id=?",
        (when or _now(), mode, paiement_id),
    )
    conn.commit()


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


def delete_paiement(conn: sqlite3.Connection, paiement_id: int) -> None:
    """Supprime un paiement (annulation). La trace reste dans le journal d'audit."""
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

def log_audit(conn: sqlite3.Connection, action: str, detail: str = "") -> None:
    """Consigne une action (best-effort : ne jamais faire echouer l'appelant)."""
    try:
        conn.execute(
            "INSERT INTO audit_log (action, detail) VALUES (?, ?)",
            (action, detail or ""),
        )
        conn.commit()
    except sqlite3.Error:
        pass


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
