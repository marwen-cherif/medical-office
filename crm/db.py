"""Acces SQLite : connexion, schema et migrations legeres.

Base locale mono-fichier (data/cabinet.db par defaut). Aucune dependance
externe : uniquement le module standard sqlite3.
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = 11


class SchemaTooNewError(RuntimeError):
    """La base vient d'une version plus recente de l'application.

    Ouvrir une base plus recente avec un schema plus ancien risquerait d'ecraser
    ou de perdre des donnees : on refuse de continuer plutot que de degrader la
    base. Voir la garde anti-downgrade dans `connect()`.
    """

    def __init__(self, disk_version: int, app_version: int) -> None:
        self.disk_version = disk_version
        self.app_version = app_version
        super().__init__(
            f"Base en version {disk_version}, application en version {app_version}."
        )


def app_dir() -> Path:
    """Dossier de l'application (a cote de l'exe une fois gele, sinon racine projet)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def default_db_path() -> Path:
    return app_dir() / "data" / "cabinet.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nom             TEXT NOT NULL,
    prenom          TEXT NOT NULL,
    slug_nom        TEXT NOT NULL,
    slug_prenom     TEXT NOT NULL,
    date_naissance  TEXT,
    email           TEXT,
    telephone       TEXT,
    adresse         TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_patients_slug ON patients(slug_nom, slug_prenom);

CREATE TABLE IF NOT EXISTS documents (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id           INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    type                 TEXT NOT NULL,
    template             TEXT,
    acte                 TEXT,
    montant              REAL,
    acte_date            TEXT,
    file_path            TEXT,
    output_format        TEXT NOT NULL DEFAULT 'jpg',
    statut               TEXT NOT NULL DEFAULT 'genere',
    date_generation      TEXT,
    date_envoi           TEXT,
    email                TEXT,
    mailjet_message_id   TEXT,
    mailjet_status       TEXT,
    date_refresh_status  TEXT,
    message_erreur       TEXT,
    created_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_documents_patient ON documents(patient_id);

CREATE TABLE IF NOT EXISTS paiements (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id          INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    document_id         INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    montant             REAL NOT NULL DEFAULT 0,
    statut              TEXT NOT NULL DEFAULT 'en_attente',
    mode                TEXT,
    date_echeance       TEXT,
    date_encaissement   TEXT,
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_paiements_patient ON paiements(patient_id);

CREATE TABLE IF NOT EXISTS mail_templates (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    name                 TEXT NOT NULL,
    mailjet_template_id  INTEGER NOT NULL,
    is_default           INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS template_fields (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name  TEXT NOT NULL,
    tag            TEXT NOT NULL,
    label          TEXT,
    type           TEXT NOT NULL DEFAULT 'text',
    default_value  TEXT,
    sort_order     INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_template_fields_name ON template_fields(template_name);

CREATE TABLE IF NOT EXISTS jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    kind         TEXT NOT NULL,              -- 'generation' | 'envoi'
    doc_type     TEXT NOT NULL,             -- type de document cible
    statut       TEXT NOT NULL DEFAULT 'en_cours',  -- en_cours | termine | erreur
    total        INTEGER NOT NULL DEFAULT 0,
    done         INTEGER NOT NULL DEFAULT 0,
    ok           INTEGER NOT NULL DEFAULT 0,
    skipped      INTEGER NOT NULL DEFAULT 0,
    errors       INTEGER NOT NULL DEFAULT 0,
    params       TEXT,                       -- JSON (date_from/date_to/mail_template_id)
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at  TEXT
);

CREATE TABLE IF NOT EXISTS job_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    patient_id   INTEGER,
    document_id  INTEGER,
    statut       TEXT NOT NULL,              -- ok | skip | erreur
    message      TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_job_items_job ON job_items(job_id);

-- v11 : `patient_id` rattache un evenement a une fiche (NULL = evenement global,
-- ex. demarrage) et `detail` heberge desormais un JSON structure. Pas de FK sur
-- `patient_id` : log_audit reste best-effort et certaines lignes sont globales ou
-- anterieures (NULL). Voir openspec/changes/refonte-fiche-patient.
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL DEFAULT (datetime('now')),
    action      TEXT NOT NULL,
    detail      TEXT,
    patient_id  INTEGER
);

CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);
-- idx_audit_patient est cree dans _migrate(), APRES l'ajout de la colonne
-- patient_id : sur une base anterieure, audit_log existe deja sans cette colonne,
-- donc le CREATE INDEX ne peut pas s'executer ici (avant l'ALTER).

CREATE TABLE IF NOT EXISTS meta (
    key    TEXT PRIMARY KEY,
    value  TEXT
);

-- v6 : suivi des depenses fournisseurs (factures importees + reglements partiels).
-- Evolution PUREMENT ADDITIVE : ces tables n'existaient pas avant ; `documents`
-- (notes patients) n'est pas touchee. Voir prd_depenses.md / spec_technique_depenses.md.
CREATE TABLE IF NOT EXISTS prestataires (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    nom          TEXT NOT NULL,
    prenom       TEXT NOT NULL DEFAULT '',
    slug_nom     TEXT NOT NULL,
    slug_prenom  TEXT NOT NULL,
    email        TEXT,
    telephone    TEXT,
    adresse      TEXT,
    notes        TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_prestataires_slug ON prestataires(slug_nom, slug_prenom);

-- Facture fournisseur IMPORTEE (PDF/image archive). Pas de generation Word, pas d'envoi.
CREATE TABLE IF NOT EXISTS factures (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    prestataire_id  INTEGER NOT NULL REFERENCES prestataires(id) ON DELETE CASCADE,
    fichier         TEXT NOT NULL,
    nom_original    TEXT,
    montant         REAL,
    libelle         TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_factures_prestataire ON factures(prestataire_id);

-- Depense (sortie d'argent) avec reglement partiel : montant du, cumul regle, reste derive.
CREATE TABLE IF NOT EXISTS depenses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    prestataire_id  INTEGER NOT NULL REFERENCES prestataires(id) ON DELETE CASCADE,
    facture_id      INTEGER REFERENCES factures(id) ON DELETE SET NULL,
    montant         REAL NOT NULL DEFAULT 0,
    montant_regle   REAL NOT NULL DEFAULT 0,
    statut          TEXT NOT NULL DEFAULT 'en_attente',  -- en_attente | regle_partiellement | regle
    mode            TEXT,
    motif           TEXT,
    date_echeance   TEXT,
    date_paiement   TEXT,
    libelle         TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_depenses_prestataire ON depenses(prestataire_id);

-- v7 : historique des reglements d'une depense (1 ligne par versement, datee).
-- Permet le vrai flux de tresorerie par date de transaction (date_reglement),
-- y compris pour les reglements partiels. `depenses.montant_regle` reste le cumul
-- (source de verite du solde) ; cette table est l'historique detaille.
CREATE TABLE IF NOT EXISTS depense_reglements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    depense_id      INTEGER NOT NULL REFERENCES depenses(id) ON DELETE CASCADE,
    montant         REAL NOT NULL,
    mode            TEXT,
    motif           TEXT,
    date_reglement  TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_depense_reglements_depense ON depense_reglements(depense_id);
CREATE INDEX IF NOT EXISTS idx_depense_reglements_date ON depense_reglements(date_reglement);

-- v8 : categorisation des modeles de documents. La categorie est un attribut de
-- MODELE porte par l'application (pas dans le .docx). Evolution PUREMENT ADDITIVE :
-- ces tables n'existaient pas avant ; `documents` recoit en plus une colonne nullable
-- `categorie` (snapshot a la generation, cf. _migrate). Voir
-- openspec/changes/organize-documents-by-category.
-- Association modele -> categorie courante (cle naturelle = nom du modele).
-- Absence de ligne = modele sans categorie.
CREATE TABLE IF NOT EXISTS template_meta (
    template_name  TEXT PRIMARY KEY,
    categorie      TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Attributs visuels et ordre d'affichage par categorie (creee paresseusement
-- quand une nouvelle categorie apparait, couleur par defaut depuis une palette).
CREATE TABLE IF NOT EXISTS categories (
    nom         TEXT PRIMARY KEY,
    couleur     TEXT,
    icone       TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- v9 : referentiel d'actes tarifes (libelle + prix). Source de prix reutilisable
-- pour pre-remplir des montants ailleurs (plans de traitement, facturation
-- multi-lignes). Evolution PUREMENT ADDITIVE : table neuve creee par _SCHEMA ;
-- aucune donnee existante (documents/paiements) touchee. Retrait NON destructif
-- via `actif` (l'acte disparait des listes de saisie mais reste en base, pour ne
-- pas casser un eventuel snapshot historique). `slug_libelle` = recherche
-- insensible aux accents (meme approche que patients/prestataires). Voir
-- openspec/changes/referentiel-actes.
CREATE TABLE IF NOT EXISTS actes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    libelle       TEXT NOT NULL,
    slug_libelle  TEXT NOT NULL,
    prix          REAL NOT NULL DEFAULT 0,
    code          TEXT,
    actif         INTEGER NOT NULL DEFAULT 1,
    sort_order    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_actes_slug ON actes(slug_libelle);
CREATE INDEX IF NOT EXISTS idx_actes_actif ON actes(actif);

-- v10 : plans de traitement (regroupement nomme d'actes d'un patient), actes
-- realises (`prestations` : du + reglement partiel, calque de `depenses`) et
-- historique des reglements d'actes. Evolution PUREMENT ADDITIVE : trois tables
-- neuves creees par _SCHEMA ; `paiements` / `documents` ne sont PAS touchees.
-- `prestations.plan_id` est nullable (acte ISOLE = sans plan) avec
-- `ON DELETE SET NULL` : supprimer un plan DETACHE ses actes (ils deviennent
-- isoles) au lieu de les detruire (D8). PAS de colonne `type` : un controle est
-- un acte a montant nul (D5, non facturable derive). Le prix est un SNAPSHOT
-- recopie depuis le referentiel d'actes (D3). Voir
-- openspec/changes/plans-de-traitement.
CREATE TABLE IF NOT EXISTS plans_traitement (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id  INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    titre       TEXT NOT NULL,
    notes       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_plans_patient ON plans_traitement(patient_id);

-- Acte realise sur un patient : porte a la fois le DU (`montant`) et le PAIEMENT
-- (`montant_regle` cumul, `statut`, reste derive) — calque de `depenses`.
CREATE TABLE IF NOT EXISTS prestations (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id     INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    plan_id        INTEGER REFERENCES plans_traitement(id) ON DELETE SET NULL,
    acte_id        INTEGER,
    libelle        TEXT NOT NULL,
    montant        REAL NOT NULL DEFAULT 0,
    montant_regle  REAL NOT NULL DEFAULT 0,
    statut         TEXT NOT NULL DEFAULT 'en_attente',  -- en_attente | regle_partiellement | regle
    date_acte      TEXT,
    dents          TEXT,
    note           TEXT,
    sort_order     INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_prestations_patient ON prestations(patient_id);
CREATE INDEX IF NOT EXISTS idx_prestations_plan ON prestations(plan_id);

-- Historique des reglements d'un acte (1 ligne par versement, datee) : calque de
-- `depense_reglements`. `prestations.montant_regle` reste le cumul (source du solde).
CREATE TABLE IF NOT EXISTS prestation_reglements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    prestation_id   INTEGER NOT NULL REFERENCES prestations(id) ON DELETE CASCADE,
    montant         REAL NOT NULL,
    mode            TEXT,
    date_reglement  TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_prestation_reglements_prestation ON prestation_reglements(prestation_id);
CREATE INDEX IF NOT EXISTS idx_prestation_reglements_date ON prestation_reglements(date_reglement);
"""


def _read_schema_version(path: Path) -> int | None:
    """Lit meta.schema_version d'une base existante SANS la modifier.

    Renvoie None si la base n'existe pas, n'a pas encore de table `meta`, ou ne
    contient pas la cle (anciennes bases anterieures au suivi de version).
    """
    if not path.exists():
        return None
    ro: sqlite3.Connection | None = None
    try:
        ro = sqlite3.connect(path)
        row = ro.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else None
    except (sqlite3.Error, TypeError, ValueError):
        return None
    finally:
        if ro is not None:
            ro.close()


def _snapshot_before_migration(path: Path, disk_version: int | None) -> None:
    """Copie etiquetee de la base AVANT migration, conservee hors purge.

    Filet de securite quand le schema evolue : si une migration tourne mal, on
    garde l'etat exact d'avant dans `backups/pre-migration/`. Ce dossier n'est
    PAS balaye par `backup._prune` (qui ne regarde que `backups/cabinet-*.db`),
    donc ces copies survivent a la rotation KEEP=10. Best-effort : ne leve pas.
    """
    try:
        dest_dir = app_dir() / "backups" / "pre-migration"
        dest_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        frm = disk_version if disk_version is not None else "x"
        dest = dest_dir / f"cabinet-v{frm}-to-v{SCHEMA_VERSION}-{stamp}.db"
        shutil.copy2(path, dest)
    except OSError:
        pass


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Ouvre (et cree si besoin) la base, applique le schema, renvoie la connexion.

    Avant toute migration : refuse une base plus recente que l'application
    (garde anti-downgrade, leve `SchemaTooNewError`) et, si la base est plus
    ancienne, en fait une copie etiquetee (filet de securite pre-migration).
    """
    path = db_path or default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    disk_version = _read_schema_version(path)
    if disk_version is not None and disk_version > SCHEMA_VERSION:
        raise SchemaTooNewError(disk_version, SCHEMA_VERSION)
    if path.exists() and (disk_version is None or disk_version < SCHEMA_VERSION):
        _snapshot_before_migration(path, disk_version)

    # check_same_thread=False : l'UI Flet execute les travaux bloquants (generation
    # Word/PDF, envoi email) dans un thread d'arriere-plan pour ne pas figer la
    # fenetre. L'acces concurrent est evite par la garde `_busy` cote app (un seul
    # travail a la fois) et par les dialogues modaux pendant ces operations.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Un job tourne en arriere-plan pendant que l'UI reste navigable : laisser
    # SQLite reessayer brievement en cas de verrou plutot que d'echouer aussitot.
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.executescript(_SCHEMA)
    _migrate(conn)
    _set_version(conn)
    conn.commit()
    return conn


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def _meta_get(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def _meta_set(conn: sqlite3.Connection, key: str, value: str = "1") -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _migrate(conn: sqlite3.Connection) -> None:
    """Migrations idempotentes pour les bases existantes (executescript ne fait pas d'ALTER)."""
    # v2 : valeurs de variables saisies, stockees en JSON sur chaque document.
    if not _column_exists(conn, "documents", "variables"):
        conn.execute("ALTER TABLE documents ADD COLUMN variables TEXT")
    # v5 : suivi Mailjet detaille (horodatage premiere ouverture / premier clic).
    if not _column_exists(conn, "documents", "mailjet_opened_at"):
        conn.execute("ALTER TABLE documents ADD COLUMN mailjet_opened_at TEXT")
    if not _column_exists(conn, "documents", "mailjet_clicked_at"):
        conn.execute("ALTER TABLE documents ADD COLUMN mailjet_clicked_at TEXT")
    # v7 : backfill de l'historique des reglements pour les depenses deja (partiellement)
    # reglees AVANT l'introduction de la table (la table elle-meme est creee par _SCHEMA).
    # 1 ligne resumant le cumul, datee du dernier reglement (sinon de la creation).
    # Idempotent : sentinelle meta + garde NOT IN (ne duplique jamais).
    if _meta_get(conn, "reglements_backfill_v7") is None:
        conn.execute(
            "INSERT INTO depense_reglements (depense_id, montant, mode, motif, date_reglement) "
            "SELECT id, montant_regle, mode, motif, COALESCE(date_paiement, created_at) "
            "FROM depenses WHERE montant_regle > 0 "
            "AND id NOT IN (SELECT depense_id FROM depense_reglements)"
        )
        _meta_set(conn, "reglements_backfill_v7")
    # v8 : snapshot de la categorie du modele sur chaque document a la generation.
    # Colonne additive nullable : les documents existants gardent categorie NULL
    # (ranges a la racine du dossier patient). Aucun backfill destructif.
    if not _column_exists(conn, "documents", "categorie"):
        conn.execute("ALTER TABLE documents ADD COLUMN categorie TEXT")
    # v9 : referentiel d'actes. Aucune transformation ici : la table `actes` est
    # neuve et entierement creee par _SCHEMA (CREATE TABLE IF NOT EXISTS). Le bump
    # de SCHEMA_VERSION 8 -> 9 declenche a lui seul le snapshot pre-migration dans
    # connect() pour toute base ouverte en v8 (cf. _snapshot_before_migration).
    # v10 : plans de traitement / prestations / prestation_reglements. Aucune
    # transformation ici : les trois tables sont neuves et entierement creees par
    # _SCHEMA (CREATE TABLE IF NOT EXISTS) ; `paiements` / `documents` ne sont pas
    # touchees. Le bump SCHEMA_VERSION 9 -> 10 declenche a lui seul le snapshot
    # pre-migration dans connect() pour toute base ouverte en v9.
    # v11 : journal d'audit par patient. Colonne additive nullable `patient_id`
    # (sans FK) + index de lecture par patient. Idempotent (garde _column_exists,
    # index IF NOT EXISTS). Les anciennes lignes gardent patient_id NULL et un
    # `detail` texte libre (toleres a la lecture, cf. repo.parse_audit_detail). Le
    # bump SCHEMA_VERSION 10 -> 11 declenche le snapshot pre-migration dans connect().
    if not _column_exists(conn, "audit_log", "patient_id"):
        conn.execute("ALTER TABLE audit_log ADD COLUMN patient_id INTEGER")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_patient ON audit_log(patient_id, id DESC)"
    )


def _set_version(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES ('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(SCHEMA_VERSION),),
    )
