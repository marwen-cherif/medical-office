## 1. Service de fond — worker tray windowed (`apps/api/crm/`)

- [x] 1.1 Créer `crm/autostart.py` : inscription idempotente du worker dans
  `HKCU\…\Run` (valeur `CabinetCRM-Tray`), `install()` / `uninstall()` /
  `is_installed()` (détection de valeur obsolète), `cleanup_legacy_task()` qui
  supprime l'ancienne tâche `schtasks` `CabinetCRM-RappelsService`. Best-effort,
  ne lève jamais.
- [x] 1.2 Créer `crm/tray.py` : worker windowed — boucle scheduler interne
  (thread daemon appelant `service.run_once()` à `rappels_scheduler_interval`),
  icône tray `pystray` (menu « Ouvrir / Statut / Quitter », double-clic = ouvrir),
  mutex singleton Win32 nommé `Local\tn.cabinet.gouiaaa.crm.tray`, fallback
  icône PIL, journalisation via `service._setup_logging`.
- [x] 1.3 Refactor `crm/service.py` : extraire `run_once()` (un cycle, renvoie
  `(code, rappels_traités)`) de `run()` (compat one-shot) ; ajouter
  `creationflags=CREATE_NO_WINDOW` sur le sous-processus PowerShell des toasts ;
  mettre à jour les docstrings (« tâche planifiée » → « worker tray »).
- [x] 1.4 Supprimer `crm/scheduler.py` (toute la logique `schtasks`).
- [x] 1.5 Mettre à jour `crm/server.py` : remplacer `ensure_scheduled_task(conn)`
  par `autostart.install()` au démarrage (best-effort) ; migrer les endpoints
  `/api/settings/rappels*` (GET, PUT, POST `install-task`) vers `autostart`
  (champs `task_*` conservés pour compat frontend) ; convertir `--service` en
  alias du worker tray.

## 2. Build & packaging du worker (`apps/api/`, `apps/web/src-tauri/`)

- [x] 2.1 Créer l'entry point `apps/api/crm_tray.py` (`from crm.tray import run`).
- [x] 2.2 Créer `apps/api/crm-tray.spec` (PyInstaller, `console=False`,
  hiddenimports `pystray`/`PIL`/`crm.*`, datas `logo.ico`, excludes
  `fastapi`/`uvicorn`/`starlette`).
- [x] 2.3 Nettoyer le commentaire de `apps/api/crm-server.spec` (préciser que
  le service de fond est désormais `crm-tray.exe`, pas `crm-server.exe`).
- [x] 2.4 Mettre à jour `apps/api/scripts/copy-sidecar.js` : copier
  `crm-server` **et** `crm-tray` dans `src-tauri/binaries/`.
- [x] 2.5 Mettre à jour `apps/web/src-tauri/tauri.conf.json` : `externalBin`
  ajoute `binaries/crm-tray`.
- [x] 2.6 Mettre à jour `apps/api/package.json` (`build` lance les deux specs)
  et `apps/api/requirements.txt` (ajout `pystray>=0.19`).

## 3. Tests du worker (`apps/api/crm/tests/`)

- [x] 3.1 `test_autostart.py` : mock `winreg` + `sys.frozen`, couvre
  `_tray_command` (dev/frozen), `install` / `is_installed` / `uninstall`
  (roundtrip, idempotence, valeur obsolète), `cleanup_legacy_task` (tâche
  absente/présente).
- [x] 3.2 `test_tray.py` : mock mutex Win32 (1re instance / déjà lancé),
  boucle scheduler (un cycle puis stop, survie aux exceptions, arrêt immédiat
  pendant le sleep).
- [x] 3.3 Vérifier le lint ruff (mes fichiers propres) et `tsc --noEmit` du
  frontend ; relancer la suite complète (`103 passed`).

## 4. Frontend — libellés worker tray (`apps/web/src/`)

- [x] 4.1 `screens/parametrage/RappelsTab.tsx` : bloc « Tâche planifiée Windows »
  → « Service de fond » (worker `crm-tray.exe`), boutons « Installer /
  Réinstaller le service », texte d'aide mis à jour. Champs `task_*` inchangés
  (compat API).

## 5. Installer NSIS custom — détection + préservation (`apps/web/src-tauri/`)

- [x] 5.1 Créer le template `config.default.ini` (sans secrets) à côté de
  `config.ini` dans `apps/api/` (source de vérité des valeurs par défaut de
  migration). Le référencer comme `resources` dans `tauri.conf.json` pour
  embarquement.
- [x] 5.2 Configurer `bundle.windows.nsis` dans `tauri.conf.json`
  (`installMode: currentUser`, `installerHooks` ou `template` pointant vers un
  `.nsi` custom). Définir le chemin d'install par défaut
  `%LOCALAPPDATA%\Cabinet CRM`.
- [x] 5.3 Écrire le `.nsi` custom : hook `NSIS_HOOK_PREINSTALL` qui `taskkill
  /IM crm-tray.exe /IM "Cabinet CRM.exe"` avant copie ; écriture de
  `HKCU\Software\Cabinet CRM` (`InstallPath`, `InstallVersion`) après install ;
  préservation de `config.ini` existant (copie `config.default.ini` seulement
  si `config.ini` absent) ; hook de désinstallation qui supprime
  `HKCU\…\Run\CabinetCRM-Tray` et la clé `Software\Cabinet CRM`.
- [x] 5.4 Page NSIS de confirmation du dossier détecté (lecture de
  `InstallPath` au registre, pré-remplie ; install fraîche si absent).


## 6. Migration de configuration versionnée (`apps/api/`)

- [x] 6.1 Créer `crm/config_migrate.py` : `CONFIG_VERSION` (entier) + fonction
  `migrate(config_path, default_path)` qui fusionne les clés manquantes depuis
  `config.default.ini` sans toucher aux valeurs existantes, en s'appuyant sur
  le commentaire `; config_version = N` en tête de `config.ini`. Idempotent,
  best-effort, journalisé.
- [x] 6.2 Appeler `config_migrate.migrate()` au démarrage de l'app
  (`crm/server.py`) avant `load_config()`, avec snapshot pré-migration
  `config.pre-v<N>.ini` (modèle calqué sur `db.py`).
- [x] 6.3 `crm/tests/test_config_migrate.py` : ajout de clés nouvelles,
  préservation des secrets existants, idempotence, version absente
  (première install), garde anti-downgrade.


## 7. Vérification de bout en bout

- [x] 7.1 Build local : `npm run build` côté `apps/api` (deux exes) puis
  `apps/web` (installer NSIS custom).
- [x] 7.2 Install fraîche sur VM propre : `config.default.ini` copié comme
  `config.ini`, worker tray démarre au logon sans flash, icône présente,
  clé `HKCU\…\Run` posée sans UAC.
- [x] 7.3 Mise à jour par-dessus l'ancienne version : tâche `schtasks`
  supprimée, `config.ini` préservé, nouvelles clés migrées au premier
  démarrage, ancienne donnée `data/` intacte.
- [x] 7.4 Scénario rappel échu app fermée → toast sans flash console,
  persistance dans le Centre de notifications.
- [x] 7.5 Menu tray : « Quitter » kill proprement, « Ouvrir » lance l'app,
  « Statut » affiche l'heure du prochain check.
