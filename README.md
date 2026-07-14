# CRM & Fee Note Generator

A modern desktop and web application designed for Dr. Aslem Gouiaa's medical office. It manages a local repository of patients, generates documents (fee notes, letters, etc.) in **JPG or PDF** format from Word templates using MS Word COM automation, sends them via **Mailjet**, and tracks email delivery status.

This application is built as a monorepo containing a **React (Vite + Tailwind CSS v4)** frontend packaged in a **Tauri** desktop wrapper, communicating with a **FastAPI** backend sidecar. All data is stored in a **local SQLite database** (`apps/api/data/cabinet.db`)—fully local, no cloud storage.

---

## Prerequisites

- **Windows 10 or 11**
- **Microsoft Word** installed locally (required to render templates using COM automation)
- **Node.js** (v20+ recommended) and **pnpm** (v11+ recommended) installed (for building and running)
- **Python 3.11+** installed on your system PATH
- A **Mailjet account** (https://app.mailjet.com) with:
  - An API key + secret key (Account -> API Key Management)
  - A validated sender email address

---

## Configuration (`apps/api/config.ini`)

Copy or edit `apps/api/config.ini` to configure the application parameters:

- `mailjet.api_key` and `mailjet.api_secret`: Your credentials from the Mailjet dashboard.
- `mailjet.from_email`: A validated email sender address in Mailjet.
- `mailjet.from_name`: The display name used for sent emails.
- `mailjet.sandbox = true`: Enable sandbox mode to test without actually sending emails.
- `paths.output_format`: `jpg` (default) or `pdf` for the generated documents.
- `mail.template_id`: The ID of the Mailjet transactional template used to send emails (design and layout are managed inside Mailjet). Variables available inside the template: `{{var:prenom}}`, `{{var:nom}}`, `{{var:montant}}`, `{{var:acte}}`, `{{var:date}}`, `{{var:type_document}}`.

> [!IMPORTANT]
> `config.ini` contains sensitive Mailjet API credentials. It is listed in `.gitignore` and must never be checked into version control.

---

## Architecture Overview

This project is configured as a Turborepo monorepo:

- **`apps/web/`**: The frontend React app (Vite + TS) and the Tauri desktop wrapper.
- **`apps/api/`**: The backend Python app (FastAPI) which acts as the desktop sidecar.
- **Root Tasks**: Managed globally using `pnpm` and `turbo`.

---

## Development Workflow

All commands are run from the project root.

### Install Dependencies
```bash
pnpm install
pip install -r apps/api/requirements.txt
```

### Run in Dev Mode
This command starts both the Vite web server (port `1420`) and the FastAPI backend server (port `8765`) in parallel:
```bash
pnpm run dev
```

### Run Tests
Runs backend unit tests (PyTest) and frontend unit tests (Vitest) in parallel:
```bash
pnpm run test
```

### Run Coverage Reports
Runs the test suites and prints/saves coverage metrics (`htmlcov/` for backend, `coverage/` for frontend):
```bash
pnpm run test:coverage
```

### Lint and Format
```bash
pnpm run lint     # Lint all packages
pnpm run format   # Format all source files with Prettier & Ruff
```

---

## Production Build

To package the desktop application into an installer:

```bash
pnpm run build
```

This pipeline automatically:
1. Compiles the FastAPI backend into a standalone executable using **PyInstaller**.
2. Automatically copies the sidecar binary to the correct Rust compile path inside Tauri.
3. Compiles the React frontend assets.
4. Compiles the Rust shell using **Tauri** to produce the final Windows installer `.exe`.

*Note: Building Tauri requires the Rust toolchain (`rustc`, `cargo`) to be installed and available on your system.*

---

## Utility Scripts

- **`reset.bat`** (Root): Cleans the local database and deletes generated outputs. It will ask for confirmation (type `SUPPRIMER` to confirm). To run non-interactively: `python -m crm.reset --yes` (run with PYTHONPATH set to `apps/api/`).
- **`import-actes.bat`** (Root): Interactive script to import or export the medical acts directory from/to Excel spreadsheets.

---

## Features

- **Stable Patient Directory**: Patients are assigned unique IDs. Duplicates (homonyms) are automatically detected and flagged during registration.
- **Dynamic Variable Detection**: The backend parses Word documents in `apps/api/templates/` and extracts placeholder tags `<...>`. Patient fields (`<NOM>`, `<PRENOM>`, etc.) are filled automatically, while other variables (amounts, dates) are requested interactively before generation.
- **Transactional Email Routing**: Send generated JPG/PDF documents as attachments using customizable Mailjet transaction IDs.
- **Send Status Tracking**: Fetches real-time webhook statuses (`queued`, `sent`, `opened`, `bounce`, etc.) from the Mailjet API.
- **RGPD Compliance**: All medical data is stored strictly locally. Auto-backups of the SQLite database are created on startup (retaining the 10 most recent copies in `apps/api/backups/`).
