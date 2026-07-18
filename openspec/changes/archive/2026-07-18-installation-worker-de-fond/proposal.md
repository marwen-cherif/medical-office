## Why

Le cabinet médical doit pouvoir être **notifié des rappels échus même quand
l'application est fermée** (spécification métier de la capability `rappels` :
« Présentation des rappels dus au démarrage »). L'implémentation précédente
reposait sur une **tâche planifiée Windows** (`schtasks`, nommée
`CabinetCRM-RappelsService`) qui relançait `crm-server.exe --service` toutes les
15 minutes.

Ce mécanisme présente trois défauts bloquants pour une distribution en cabinet :

1. **Flash de console noire** : `crm-server.exe` est compilé `console=True` (le
   handshake stdout avec la coquille Tauri l'exige). Or la tâche planifiée ne
   masque pas la fenêtre → une console noire apparaît fugacement toutes les
   15 minutes, **même quand l'utilisateur ne fait rien**. En mode dev, c'est
   pire (`cmd.exe` + `python.exe`). Le sous-processus PowerShell émetteur de
   toasts ajoute une troisième flash.
2. **Aucune maîtrise du cycle de vie du service de fond** : l'utilisateur ne
   peut ni l'arrêter, ni savoir s'il tourne, ni le relancer. Pas d'icône tray.
3. **Installation / mise à jour non gérées** : l'installer NSIS par défaut de
   Tauri ne détecte pas une installation existante, n'embarque pas
   `config.ini`, et **écraserait aveuglément** les secrets (clés Mailjet, API
   IA) lors d'une réinstallation. Aucun mécanisme de migration des fichiers de
   configuration entre versions n'existe.

Le besoin est donc double : un **service de fond invisible et pilotable**, et un
**installer capable de détecter l'installation existante et de préserver/migrer
la configuration** lors des mises à jour.

## What Changes

- **Remplacement de la tâche planifiée par un worker tray windowed** : un
  second exécutable `crm-tray.exe` (`console=False`, zéro flash), démarré au
  logon via `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` (**sans droits
  administrateur**), contenant sa propre boucle de planification interne et
  posant une **icône dans la zone de notification** Windows.
- **Boucle scheduler interne** : un thread daemon appelle `service.run_once()`
  toutes les `rappels_scheduler_interval` minutes (relu depuis la base à chaque
  cycle → prise en compte immédiate des changements de paramétrage).
- **Icône tray pilotable** : menu clic-droit « Ouvrir Cabinet CRM »,
  « Statut (prochain check, rappels traités) », « Quitter le service ».
  Double-clic = ouvrir l'app.
- **Anti-double-instance** : mutex Win32 nommé (`Local\tn.cabinet.gouiaaa.crm.tray`)
  garantissant un seul worker par session (évite N icônes au prochain logon).
- **Suppression de l'ancienne tâche `schtasks`** : `crm/scheduler.py` est
  supprimé ; un `cleanup_legacy_task()` best-effort supprime
  `CabinetCRM-RappelsService` au prochain démarrage pour migrer proprement.
- **Correction du flash PowerShell** : `creationflags=CREATE_NO_WINDOW` sur le
  sous-processus émetteur de toasts (`service._notify_via_powershell`).
- **Installer NSIS custom** : détection automatique du dossier d'installation
  via valeur registre posée au premier install (`HKCU\…\Uninstall\…` ou clé
  dédiée), permettant la mise à jour par simple réinstallation par-dessus.
- **Préservation de `config.ini`** : l'installer **n'écrase jamais** un
  `config.ini` existant (qui contient les secrets Mailjet / API IA). Un
  template `config.default.ini` (sans secrets) est embarqué et posé seulement
  si absent.
- **Migration de configuration par script Python** : au premier démarrage
  d'une version mise à jour, un script fusionne les nouvelles clés requises
  (depuis `config.default.ini`) dans le `config.ini` existant **sans toucher
  aux valeurs déjà renseignées**. Piloté par un numéro de version de config
  (modèle calqué sur `SCHEMA_VERSION` de `crm/db.py`).
- **Cycle de vie du worker à l'install/désinstall** : l'installer tue
  proprement tout `crm-tray.exe` en cours avant la copie des fichiers (sinon le
  fichier est verrouillé), et nettoie la valeur `HKCU\…\Run` à la désinstallation.

## Capabilities

### New Capabilities

- `service-de-fond-windows` : Service de fond Windows pour les rappels — worker
  tray windowed (`crm-tray.exe`), démarrage automatique au logon sans
  administrateur, boucle scheduler interne, icône tray pilotable, notifications
  transparentes (aucune fenêtre console).
- `installation-mise-a-jour` : Installation et mise à jour de l'application via
  un installer NSIS — auto-détection du dossier existant par registre, install
  ou update selon le cas, préservation des secrets `config.ini`, migration des
  fichiers de configuration entre versions.

### Modified Capabilities

- `rappels` : Le mécanisme d'exécution des rappels en arrière-plan change de
  support (tâche planifiée `schtasks` → worker tray). Les exigences métier des
  rappels (création, états, échéances) restent inchangées ; seul le dispositif
  de déclenchement hors-ligne est impacté. Le réglage `rappels_scheduler_interval`
  est désormais relu à chaque cycle par le worker, sans nécessité de
  réinstallation. Le bouton « Installer/Réinstaller la tâche » de l'écran de
  paramétrage devient « Installer/Réinstaller le service ».

## Impact

- **Backend Python (`apps/api/crm/`)** : nouveau module `crm/autostart.py`
  (inscription `HKCU\…\Run`), nouveau module `crm/tray.py` (worker + boucle +
  icône tray), refactor de `crm/service.py` (`run()` → `run_once()` +
  `CREATE_NO_WINDOW`), suppression de `crm/scheduler.py`, wiring dans
  `crm/server.py` (démarrage, endpoints `/api/settings/rappels*`, dispatch
  `--service`). Nouveau script de migration config (`crm/config_migrate.py`).
- **Build / Packaging** : nouveau spec PyInstaller `crm-tray.spec`
  (`console=False`), entry point `crm_tray.py`, mise à jour de
  `scripts/copy-sidecar.js` (copie des deux exes), `tauri.conf.json`
  (`externalBin` ajoute `crm-tray`), `package.json` (build lance les deux specs),
  `requirements.txt` (ajout `pystray`). Nouveau template `config.default.ini`.
- **Installer NSIS** : nouveau template `.nsi` custom (hooks
  `NSIS_HOOK_PREINSTALL` / `NSIS_HOOK_POSTINSTALL`, page de détection, kill du
  worker, écriture/lecture registre), config `bundle.windows.nsis` dans
  `tauri.conf.json`.
- **Frontend (`apps/web/src/`)** : libellés de `RappelsTab.tsx` (« Tâche
  planifiée Windows » → « Service de fond ») ; champs `task_*` conservés pour
  compatibilité API mais sémantiquement réaffectés au worker tray.
- **Dépendances** : ajout de `pystray>=0.19` (icône tray). `Pillow` déjà
  présent (impression + fallback icône).
- **Tests** : nouveaux `crm/tests/test_autostart.py` (10 cas), `crm/tests/
  test_tray.py` (6 cas), `crm/tests/test_config_migrate.py` (fusion de clés).
