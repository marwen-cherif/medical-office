# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Windows desktop tool for a dental practice ("Cabinet Dr Aslem Gouiaa") that turns a
list of patients into per-patient billing notes ("notes d'honoraires") rendered from a
Word template (output JPG or PDF), then emails each one via **Mailjet** and tracks
delivery/open status.

The app is a **Flet GUI** (`crm/`) — a desktop window or a browser app — backed by a
local SQLite database. It sits on top of a **shared generation/mail engine** (`src/`)
that drives Word and Mailjet.

> A historical CLI front-end (batch tool driven by an Excel workbook) used to live
> alongside the CRM. It has been removed; only the CRM and its shared engine remain.

Most user-facing text, comments, and identifiers are in French. Match that when editing.

## Platform constraints (important)

- **Windows only.** Document generation drives **Microsoft Word via COM**
  (`win32com.client.DispatchEx("Word.Application")` in `src/doc_filler.py`). Word must be
  installed. Generation cannot run on Linux/macOS or in CI.
- Python is needed only for dev and for building the `.exe`s, not on the end-user's
  machine once built.

## Commands

Run from the project root. No test suite exists.

```powershell
python -m pip install -r requirements.txt   # install deps

# Run in dev (no build)
python crm_app.py         # CRM desktop window (Flet)
python crm_web.py         # CRM in browser (set CRM_WEB=1 internally)
python -m crm.reset       # wipe the SQLite DB + generated notes (asks confirmation)

# Build Windows executables (PyInstaller, Windows + Word required)
.\build-crm.bat           # -> dist\Cabinet-CRM.exe + dist\Cabinet-CRM-Web.exe
```

Double-clickable `.bat` wrappers exist for non-technical use: `run-crm.bat` /
`run-crm-web.bat` (install deps + launch) and `reset.bat` (confirmed wipe). `reset.bat`
prefers the built `Cabinet-CRM.exe --reset --yes` if present, else falls back to
`python -m crm.reset --yes`. The frozen exe accepts `--reset` (optionally with `--yes`)
as an entry-point flag handled in `crm_app.py` before the GUI starts; `crm.reset` itself
takes `--yes` to skip the `SUPPRIMER` confirmation.

CRM web env vars (`crm_web.py`, `crm/app.py`): `CRM_PORT` (default 8550),
`CRM_HOST=0.0.0.0` to expose on the LAN.

## Configuration

`config.ini` (loaded by `src/config.py`, copied next to the `.exe` at build time) holds
Mailjet credentials, the sender address, output format (`jpg`/`pdf`), and the Mailjet
**transactional template id** used for email bodies. Paths in it resolve relative to the
app dir — which is the exe's folder when frozen (`sys.frozen`), else the project root
(see `_app_dir()` in `src/config.py` and `app_dir()` in `crm/db.py`).

> Note: `config.ini` holds live Mailjet API keys and is **git-ignored** (never committed —
> verified absent from history). Treat the keys as secrets — don't echo them, and flag if
> asked to share/commit them or to remove `config.ini` from `.gitignore`.

## Architecture

### Shared generation/mail engine (`src/`)

`src/` is the library the CRM builds on. It is intentionally kept independent of the UI:

- `src/doc_filler.py` — `WordSession` plus the tag-filling logic. Fills `<TAG>`
  placeholders in the `.docx` (handling tags split across Word runs, headers/footers, and
  text boxes), and exports a PDF via Word. Also exposes `extract_placeholders` and
  `format_montant` (French amount formatting: space thousands, comma decimal).
- `src/pdf_to_jpg.py` — PyMuPDF/`fitz`; rasterizes page 1 of the PDF to JPG when the
  output format is JPG.
- `src/mailer.py` — `MailjetClient` (Send API v3.1 with the note attached) plus status
  polling: each `MessageID` is polled for status (`opened`/`clicked`/`bounce`/…),
  skipping statuses already considered final (`MAILJET_FINAL_STATUSES`).
- `src/config.py` — loads `config.ini` into `Config` / `Mail` / `Mailjet`.
- `src/ui.py` — a small ANSI-colored terminal UI layer (banners, sections, colored log
  formatter), used by `crm/reset.py`. Keep its French, low-key styling when touching it.

### CRM state: SQLite (`crm/`)

The CRM keeps its state in **`data/cabinet.db`** and reuses the `src/` engine
(`src.doc_filler`, `src.mailer`, `src.pdf_to_jpg`, `src.config`):
- `crm/db.py` — connection, schema, and lightweight forward migrations. Each
  `_migrate()` step is idempotent, guarded by an existence check (`_column_exists`), so it
  is safe to re-run on any prior version. `SCHEMA_VERSION` is stored in `meta` and enforced
  on open: `connect()` refuses a DB newer than the app (anti-downgrade, raises
  `SchemaTooNewError`) and writes a labeled pre-migration snapshot when upgrading. Bump
  `SCHEMA_VERSION` and add a migration step when changing the schema.
- `crm/repo.py` — dataclasses + CRUD (patients, documents, paiements, template fields).
  Patients get a stable `id`; `slugify` + name matching detects likely duplicates so the
  user can reuse an existing record (homonym handling is user-confirmed).
- `crm/generator.py` — bridge to the `src/` engine: builds the replacement tags for a
  patient/template, renders a document, writes to `output/`, records the `documents` row,
  and sends email.
- `crm/templates.py` — manages the `templates/` folder (one `.docx` per document type),
  opening them in Word for editing. Template `<TAG>`s are auto-detected via
  `src.doc_filler.extract_placeholders`; tags in `AUTO_PATIENT_TAGS` (NOM, PRENOM, EMAIL,
  TELEPHONE, ADRESSE, DATE_NAISSANCE) are filled from the patient, the rest are prompted.
- `crm/printing.py` — impression directe des documents générés (JPG/PDF) vers une
  imprimante Windows via GDI (pywin32 `win32print`/`win32ui`, déjà embarqué pour Word) :
  pixelise le PDF avec `fitz`, met l'image à l'échelle de la page avec Pillow
  (`ImageWin.Dib`) et l'envoie sans boîte de dialogue. L'imprimante cible est choisie
  une fois dans Paramétrage › Imprimante et mémorisée dans `meta` (clé `printer_name`,
  via `repo.get_setting`/`set_setting` — pas de migration). En mode web, l'impression
  s'exécute côté serveur (machine où tourne l'app), pas dans le navigateur.
- `crm/backup.py` — timestamped copy of `cabinet.db` into `backups/` on each startup,
  keeping the latest `KEEP` (10).
- `crm/app.py` — the entire Flet UI (large single file). Palette + status-label maps live
  at the top.
- `crm/reset.py` — wipes the DB tables and generated notes (`python -m crm.reset`).

**Idempotency is filename-based.** A document's filename (derived from name + date +
format) is the key: if a file / `documents` row already exists it's skipped. Forcing a
regeneration/resend means removing the file/row or resetting its status.

### Placeholder convention

Templates use literal `<UPPERCASE_TAG>` markers (regex `<([A-Z0-9_]+)>` in
`src/doc_filler.py`). `crm/generator.py` builds the replacement map for a patient +
template, adding derived tags (e.g. ISO dates, gross amount). `format_montant`
(`src/doc_filler.py`) formats amounts in French style (space thousands, comma decimal).

## Data preservation across releases (READ before any schema/DB change)

The app ships as a replaceable `.exe`; the user's real data lives **next to it** and must
survive every update: `data/cabinet.db` (source of truth), `output/` (generated notes),
`templates/` (user-edited `.docx`), and a user-edited `config.ini`. **Every evolution must
assume an existing, populated production DB — never a fresh one.** Rules:

1. **Additive / expand-only schema.** New columns must be nullable or have a `DEFAULT`; new
   tables via `CREATE TABLE IF NOT EXISTS`. Do **not** `DROP`/`RENAME` a column or table
   holding production data in a single release (SQLite's `ALTER` is limited and the data is
   lost). To remove something, use expand → backfill → switch reads/writes → (much later)
   contract, spread across several releases.
2. **Schema change ⇒ bump `SCHEMA_VERSION` + add an idempotent step in `_migrate()`**
   (`crm/db.py`), guarded by existence checks (`_column_exists`) so it is safe to re-run on
   any prior version. Wrap data-transform migrations in a transaction and guard them on a
   `meta` sentinel so they run exactly once.
3. **Back up BEFORE migrating.** `connect()` migrates the live DB, so the backup must run
   first. Today `backup_db()` runs *after* `connect()` (`crm/app.py` ~L2844/L2847) — when
   adding a migration, take a pre-migration snapshot first and keep a labeled copy (e.g.
   `cabinet-pre-v<N>-…db`) exempt from the rolling `KEEP=10` prune.
4. **Guard against downgrade.** `SCHEMA_VERSION` is written to `meta` but never read: read
   `meta.schema_version` on startup and refuse/warn when it is **greater** than the app's
   version (DB touched by a newer build — writing with the old schema can lose data).
5. **No destructive ops in the normal flow.** No `DROP`/`DELETE`/`TRUNCATE` in migrations or
   at startup. The only destructive path is the explicit, user-confirmed `crm.reset`.
6. **Filename idempotency is data-affecting.** Changing the output filename convention or
   `output_format` makes existing notes unrecognized and regenerated — treat such changes
   as data migrations, not cosmetics.
7. **Test on a real DB before shipping.** Copy a production `cabinet.db` (from `backups/`),
   run the new build against it, and confirm existing patients/documents/paiements still
   load and render. Generation needs Windows + Word, so this is a manual pre-release gate
   (no CI can catch it).

## Gotchas

- Touching the run-splitting logic in `_replace_in_para_elem` (`src/doc_filler.py`) is
  delicate: it redistributes replacement text back across Word runs to preserve
  formatting (bold, etc.) for tags spanning multiple runs. Verify rendered output, not
  just the string result.
- `src/` is imported by `crm/` — changing its public functions/signatures affects the
  CRM. The engine is deliberately reused "without modifying it."
- Switching `output_format` changes the filename extension, so existing notes stop being
  recognized and get regenerated.
- There are two PyInstaller specs (`crm-desktop.spec`, `crm-web.spec`); `build-crm.bat`
  is the canonical build entry point.
