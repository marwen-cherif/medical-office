## Context

L'étude `etude-migration-ui-react` (archivée le 2026-06-24) a conclu **go** vers un frontend
**React** (Vite + TS + Tailwind v4 + shadcn) adossé à un **backend Python sidecar** (FastAPI)
en **HTTP localhost**, empaqueté avec **Tauri**, le moteur (`src/` + `crm/` hors `app.py`) étant
**réutilisé sans modification**. Les décisions de fond (D1 architecture, D2 React/Tauri, D3 IPC
HTTP, D4 migration incrémentale, D5 packaging, D6 stack frontend, D7 FastAPI) ainsi que la
cartographie de l'existant, la façade de services, le registre des risques et la traçabilité
sont consolidés dans l'archive `openspec/changes/archive/2026-06-24-etude-migration-ui-react/`
(notamment `cartographie.md` et `facade-services.md`).

Ce changement livre le **walking skeleton** : la première verticale fonctionnelle de bout en
bout (backend ⇄ frontend ⇄ packaging) sur l'**écran pilote Paramétrage**, choisi pour son
périmètre restreint et ses faibles dépendances tout en exerçant modèles, Word (édition),
impression (test) et CRUD. État courant : tout passe aujourd'hui par le monolithe Flet
`crm/app.py` (~6320 lignes).

## Goals / Non-Goals

**Goals :**
- Établir et **valider** la chaîne complète : façade FastAPI ⇄ client React généré ⇄ coquille
  Tauri + sidecar PyInstaller, sur un écran réel.
- Porter **Paramétrage** à parité fonctionnelle, en s'inspirant du Flet existant comme spec
  exécutable.
- **Préserver tous les invariants** (Word COM, données, idempotence, migrations, backup),
  démontrés côté backend inchangé.
- Servir de **go/no-go intermédiaire** avant d'engager le portage des écrans denses.

**Non-Goals :**
- Porter les autres écrans (Patients, Tableau de bord, Finances, Travaux, Prestataires) — incréments suivants.
- Retirer Flet ou faire la recette de parité globale (Flet reste oracle pendant la cohabitation).
- Mode web (reporté, cf. étude D2/Open Questions).
- Modifier le moteur, le schéma SQLite ou le format des `.docx`.

## Decisions

### D1 — Organisation du dépôt
- Frontend dans **`ui/`** (app Vite/React/Tauri autonome, son propre `package.json`).
- Backend de services dans **`crm/server.py`** (FastAPI) réutilisant `crm/*` + `src/*` **sans
  les modifier** ; ouvre la connexion via `crm/db.connect`, prend le backup et possède les
  données.
- *Alternative écartée :* monorepo outillé (Nx/Turborepo) — sur-dimensionné pour une app unique.

### D2 — Façade de services et contrat
- Une route par opération du catalogue `facade-services.md` (Paramétrage d'abord :
  `templates.*`, `mailTemplates.*`, `printers.*`, `actes.*`, `settings.*`, `categories.*`).
- **OpenAPI** auto-généré par FastAPI → **client TypeScript généré** (`openapi-typescript` ou
  `orval`) consommé par **TanStack Query** : types front/back toujours synchrones.
- Montants en nombres, dates en ISO sur le fil ; formatage FR à la présentation.

### D3 — Transport et opérations longues
- **HTTP 127.0.0.1**, **port éphémère** (lié au loopback), **jeton de session** transmis par la
  coquille au lancement (en-tête `Authorization`).
- Opérations longues (ici : **test imprimante**, **ouverture Word** ; génération/envoi sur
  d'autres écrans) → réponse `202` + identifiant de tâche, **progression en SSE**
  (`GET /events/{jobId}`), exécution dans un **pool de threads** (COM initialisé dans le thread
  worker). Réutilise le modèle `jobs` existant (`repo.create_job`/`add_job_item`/`finish_job`).
- *Alternative écartée :* WebSocket d'emblée — surdimensionné pour le pilote ; SSE suffit.

### D4 — Stack frontend
- **Vite + React 19 + TypeScript**, **Tailwind v4** (`@theme`) + **shadcn/ui** (composants
  copiés dans `ui/`), **TanStack Query**, **react-hook-form + zod**, **Sonner**.
- Composants transverses minimaux nécessaires au pilote : shell + `NavigationRail`, `Tabs`
  (sous-onglets Paramétrage), `Table`, `Dialog`, `Form`, `Badge`, `Select`. Thème repris de la
  palette de `crm/app.py`.
- **Versions épinglées** à l'init (compat Vite ↔ Tauri ↔ Tailwind v4 ↔ React 19 ↔ shadcn CLI).

### D5 — Packaging Windows
- **Tauri** (`externalBin`) embarque le **sidecar PyInstaller** (réutilise `crm-desktop.spec`),
  le démarre/arrête, découvre son port. WebView2 natif Win11.
- Données **à côté de l'exe** (`data/`, `output/`, `templates/`, `config.ini`) — inchangé.
- Le build Flet (`build-crm.bat`) reste valide tant que Flet cohabite.

### D6 — Cohabitation et préservation des invariants
- Flet (`crm/app.py`) **inchangé et lançable** ; les deux UI partagent backend + base ⇒ aucune
  divergence possible.
- Invariants portés par le backend inchangé (`facade-services.md` §6) : Word COM, propriété des
  données, idempotence par nom de fichier, `db.connect` (migrations + `SchemaTooNewError`),
  `backup.backup_db` avant migration.

## Risks / Trade-offs

- **Frontière IPC / packaging 2 process** (port, sidecar, jeton, Tauri+Rust+WebView2) →
  validés en bloc par le pilote ; superviser/redémarrer le sidecar ; *health-check* au
  lancement ; Electron en repli si friction. (Registre étude R2, R6, R7.)
- **COM dans un serveur asynchrone** mal initialisé → initialiser COM **dans le thread worker**,
  jamais dans la boucle ASGI ; sérialiser les opérations longues. (R4.)
- **Latence ressentie** des listes via HTTP → pagination existante + cache TanStack Query ;
  mesurer sur Paramétrage et fixer un seuil de recette. (R3.)
- **Incompatibilités de versions** (Vite/Tauri/Tailwind v4/React 19/shadcn) → épingler des
  versions stables et valider la chaîne sur le pilote avant d'industrialiser. (R10.)
- **Sur-coût du socle** (backend + frontend + packaging) pour un seul écran → assumé : c'est un
  **investissement non récurrent** qui débloque tous les écrans suivants.

## Migration Plan

1. **L0 — Backend** : `crm/server.py` (FastAPI), façade Paramétrage, OpenAPI, jeton + port
   éphémère, canal SSE, workers ; backup + migrations au démarrage.
2. **L1 — Frontend socle** : `ui/` (Vite/React/TS/Tailwind/shadcn), shell + nav, client TS
   généré + TanStack Query, thème.
3. **L2 — Tuyau + packaging + pilote** : Tauri `externalBin` + sidecar PyInstaller, découverte
   du port, cycle de vie ; **écran Paramétrage porté de bout en bout** ; recette de parité de
   l'écran contre Flet.
4. **Rollback** : Flet reste l'UI de production tant que le pilote n'est pas validé ; abandonner
   = continuer sur Flet sans perte (backend Python inchangé, aucune migration de données).

## Open Questions

- Choix exact du générateur de client TS (`openapi-typescript` vs `orval`) — à trancher à
  l'init selon l'ergonomie avec TanStack Query.
- Mécanisme précis de transmission port+jeton de la coquille Tauri au frontend (variable
  d'environnement du sidecar, fichier de handshake, ou argument) — à arbitrer au packaging.
- **Seuil de latence ressentie** acceptable pour les listes Paramétrage — à fixer comme critère
  de recette (étude R3).
