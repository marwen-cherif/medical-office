# Cabinet CRM — Frontend React (+ sidecar FastAPI)

Interface React (Vite + Tailwind v4 + shadcn/ui) du Cabinet CRM, adossée à un
**backend Python local (sidecar)** qui réutilise le moteur existant sans le
modifier. Premier incrément de la migration UI Flet → React : **walking skeleton
+ écran pilote Paramétrage** (cf. `openspec/changes/migration-ui-react`).

L'ancienne UI Flet (`crm/app.py`) **cohabite** : les deux partagent le même
backend et la même base `data/cabinet.db` — aucune divergence de données possible.

## Architecture (2 process)

```
┌────────────────────────┐        HTTP 127.0.0.1 (port éphémère)
│  Coquille Tauri (Rust)  │  ───────── Authorization: Bearer <jeton> ─────────┐
│  src-tauri/             │                                                    │
│   • spawn du sidecar    │                                                    ▼
│   • lit le handshake    │                                          ┌──────────────────┐
│   • injecte port+jeton  │     WebView2 (React/Vite, dist/)         │ Sidecar Python    │
│   • cycle de vie        │  ◄───────  window.__CRM_BACKEND__        │ crm/server.py     │
└────────────────────────┘                                          │ (FastAPI + moteur)│
                                                                     └──────────────────┘
                                                                              │
                                                                     data/ output/ templates/
                                                                     config.ini  (à côté de l'exe)
```

### Découverte du port + jeton (handshake)

Au démarrage, le sidecar se lie à un **port éphémère** sur `127.0.0.1`, génère un
**jeton de session**, puis imprime sur **stdout** :

```
CRM_SERVER_READY {"host":"127.0.0.1","port":<n>,"token":"<jeton>","version":"1.0.0"}
```

La coquille Tauri lit cette ligne (`src-tauri/src/main.rs`), puis crée la WebView
en injectant `window.__CRM_BACKEND__ = { host, port, token }` **avant** le
chargement de la page. Le frontend le lit dans `src/lib/bridge.ts` ; toutes les
requêtes `/api/*` portent l'en-tête `Authorization: Bearer <jeton>`.

### Cycle de vie du process

- **Démarrage** : Tauri `spawn` le sidecar (`externalBin`, port `0`) → attend le
  handshake → ouvre la fenêtre.
- **Arrêt** : à la sortie de l'app (`RunEvent::Exit`), Tauri **tue** le sidecar
  (`child.kill()`), pas de process orphelin.
- Le sidecar est lancé **sans fenêtre console** (le `.exe` est `console=True` pour
  un stdout valide, mais Tauri masque la console).

## Développement

Deux options.

**A. Frontend seul (Vite) + sidecar lancé à la main** — itération rapide UI :

```powershell
# Terminal 1 — sidecar sur un port/jeton fixes (pratique pour le dev)
python -m crm.server --port 8765 --token devtoken

# Terminal 2 — Vite (lit VITE_CRM_PORT/VITE_CRM_TOKEN, défaut 8765/devtoken)
cd ui
npm install
npm run dev        # http://127.0.0.1:1420
```

`src/lib/bridge.ts` retombe sur `127.0.0.1:8765` / `devtoken` si
`window.__CRM_BACKEND__` est absent (cas du dev navigateur).

**B. Tout dans Tauri** (nécessite Rust, cf. ci-dessous) :

```powershell
cd ui
npm run tauri dev   # spawn le sidecar + Vite, ouvre la fenêtre native
```

### Régénérer le client TypeScript après un changement d'API backend

```powershell
# Depuis la racine du projet (dump de l'OpenAPI sans lancer le serveur)
python -c "import json; from crm.server import app; json.dump(app.openapi(), open('ui/openapi.json','w'), ensure_ascii=False)"
cd ui && npm run gen:api
```

## Build de l'exécutable (Windows + Word)

Prérequis sur la machine de build :

- **Python** + `pip install -r requirements.txt` (PyInstaller inclus).
- **Node + npm**.
- **Rust** (rustup) + **Visual Studio Build Tools** (MSVC + Windows SDK) — requis
  par Tauri. (`tauri info` les signale s'ils manquent.)
- **WebView2** runtime (présent par défaut sur Windows 11).

Puis, depuis la racine :

```powershell
.\build-crm-react.bat
```

Le script : (1) empaquette le sidecar (`pyinstaller crm-server.spec` →
`dist/crm-server.exe`), (2) le copie en
`ui/src-tauri/binaries/crm-server-<triple>.exe` (nom attendu par `externalBin`),
(3) build le frontend et la coquille Tauri → installeur **NSIS** dans
`ui/src-tauri/target/release/bundle/nsis/`.

L'ancien build Flet (`build-crm.bat`) reste valide tant que Flet cohabite.

## Données à côté de l'exe (inchangé)

Le sidecar ouvre la base via `crm/db.connect`, qui résout les chemins par
`crm/db.app_dir()` : **dossier de l'exe** une fois gelé (`sys.frozen`), sinon
racine du projet. `data/cabinet.db`, `output/`, `templates/` et `config.ini`
résident donc à côté de l'exécutable, exactement comme le build Flet. Un
**backup pré-migration** est pris au démarrage (`backup.backup_db`) avant les
migrations (`db.connect`).
