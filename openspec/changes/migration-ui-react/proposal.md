## Why

L'étude `etude-migration-ui-react` (archivée) a tranché **go** : migrer la couche UI du
monolithe Flet (`crm/app.py`, ~6320 lignes) vers un **frontend React** adossé à un **backend
Python local (sidecar)** qui réutilise le moteur existant sans le modifier. Ce changement livre
le **premier incrément** de cette migration — un **walking skeleton** validant toute la chaîne
(backend FastAPI ⇄ frontend React ⇄ coquille Tauri) sur un **écran pilote** restreint
(**Paramétrage**), pour confirmer le go/no-go technique avant d'engager le portage des écrans
denses.

## What Changes

- **Nouveau backend de services `crm/server.py` (FastAPI)** : expose une **façade de services**
  HTTP localhost (une opération par cas d'usage UI) réutilisant `src/` + `crm/` (hors `app.py`)
  **sans les modifier** ; schéma **OpenAPI** auto-généré ; **jeton de session** + **port
  éphémère loopback** ; **canal d'événements (SSE)** pour la progression des opérations longues.
- **Nouveau frontend React** sous `ui/` : **Vite + TypeScript + Tailwind v4 + shadcn/ui**,
  **client TypeScript généré** depuis l'OpenAPI + **TanStack Query**, shell + `NavigationRail`,
  thème repris de la palette actuelle, composants transverses de base (Table, Tabs, Dialog,
  Badge, Calendar, Form, Sonner).
- **Écran pilote Paramétrage porté à parité** (modèles de documents, modèles d'email,
  imprimante, catalogue d'actes) — l'écran le plus restreint, qui exerce néanmoins les modèles,
  Word (édition), l'impression (test) et le CRUD.
- **Packaging Windows 2 process** : coquille **Tauri** (`externalBin`) + **sidecar PyInstaller**
  (réutilise `crm-desktop.spec`), découverte du port, cycle de vie du process ; données
  conservées **à côté de l'exe** (`data/`, `output/`, `templates/`, `config.ini`).
- **Cohabitation** : Flet (`crm/app.py`) **conservé intégralement** comme oracle de parité ;
  les deux UI partagent le même backend, donc **aucune divergence de données** possible. Aucune
  suppression de Flet dans ce périmètre.
- **Non inclus** (incréments ultérieurs) : portage des écrans Patients, Tableau de bord,
  Finances, Travaux, Prestataires ; recette de parité globale et **retrait de Flet** ; mode web.

## Capabilities

### New Capabilities
- `socle-react-sidecar` : architecture cible découplée **frontend React + backend Python
  sidecar** — façade de services sur HTTP localhost réutilisant le moteur inchangé, contrat IPC
  (formats, codes d'erreur, progression des opérations longues), packaging Tauri + sidecar,
  cohabitation avec Flet, et **parité fonctionnelle de l'écran pilote Paramétrage**, le tout en
  **préservant les invariants** (Windows/Word COM, propriété des données, idempotence par nom de
  fichier, migrations `SCHEMA_VERSION`/`_migrate()`, backup au démarrage).

### Modified Capabilities
<!-- Aucune. Le comportement métier (fiche-patient, plans-de-traitement, referentiel-actes,
     facturation-multi-lignes, historique-patient, selection-dents) est INCHANGÉ : seule la
     couche de présentation et son mode d'exécution évoluent. Les règles restent dans le moteur
     Python servi en sidecar. -->

## Impact

- **Ajouts** : `crm/server.py` (façade FastAPI), dossier `ui/` (app React/Tauri), spec Tauri /
  artefacts de build du sidecar, dépendances de dev (FastAPI/uvicorn côté Python ; Node + Rust
  + Tauri côté frontend).
- **Inchangé** : le **moteur** (`src/*`, `crm/db.py`, `crm/repo.py`, `crm/generator.py`,
  `crm/templates.py`, `crm/printing.py`, `crm/mailer.py`, `crm/backup.py`) devient une
  dépendance servie via IPC, **sans modification de ses signatures publiques**. `crm/app.py`
  (Flet) reste lançable pendant toute la cohabitation.
- **Build / packaging** : nouveau pipeline Tauri + sidecar PyInstaller à côté de
  `build-crm.bat` (l'ancien build Flet reste valide tant que Flet cohabite).
- **Contraintes préservées** (référentiel `etude-migration-ui-react/facade-services.md` §6) :
  Windows-only, Word COM, données à côté de l'exe, idempotence, migrations, backup, secrets
  `config.ini` côté backend. Génération/impression exigent toujours **Windows + Word** : recette
  manuelle (pas de CI).
