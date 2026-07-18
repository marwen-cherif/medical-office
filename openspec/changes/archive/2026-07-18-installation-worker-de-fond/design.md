## Context

L'application Cabinet CRM est une coquille **Tauri 2** (frontend React/Vite) qui
pilote un **sidecar Python FastAPI** (`crm-server.exe`, généré par PyInstaller)
pour la logique métier, l'impression (Word COM), l'envoi de documents (Mailjet,
WhatsApp) et désormais les **rappels automatiques**. La donnée est locale
(SQLite mono-fichier `data/cabinet.db`), les secrets dans `config.ini` (clés
Mailjet, API IA) posé **à côté de l'exe** en production.

Le besoin métier (capability `rappels`) impose la notification des rappels échus
**même quand l'application est fermée**. L'implémentation initiale utilisait une
**tâche planifiée Windows** (`schtasks /Create`) qui relançait
`crm-server.exe --service` toutes les 15 minutes. Ce choix s'est révélé
inacceptable pour une distribution en cabinet : flash de console noire toutes
les 15 minutes, absence de pilotage, et incompatibilité avec un flux de mise à
jour fiable (l'exe console ne peut pas être remplacé silencieusement).

Par ailleurs, le flux de distribution actuel est **manuel** : l'utilisateur
télécharge un installer NSIS généré par défaut par Tauri et le relance. Cet
installer par défaut ne sait pas détecter une installation préalable, n'embarque
pas `config.ini` (qui est `.gitignore`d et contient des secrets), et l'écraserait
sans précaution à la réinstallation — perte des clés Mailjet et API IA.

Ce changement adresse simultanément les deux problèmes car ils sont liés : le
passage à un worker permanent introduit la contrainte du fichier verrouillé à la
mise à jour, et la maîtrise du cycle de vie du worker passe par l'installer.

L'environnement cible est **uniquement Windows 10/11**, en session
mono-utilisateur (cabinet médical), **sans droits administrateur** disponibles
pour l'installer. Aucune cible macOS/Linux n'est visée pour ces fonctionnalités.

## Goals / Non-Goals

**Goals:**

- Aucune fenêtre console ne doit apparaître, ni au démarrage du service de fond,
  ni à chaque notification, ni en mode dev.
- L'utilisateur peut arrêter, relancer et consulter l'état du service de fond
  via une icône tray.
- Le service de fond démarre automatiquement au logon sans intervention ni
  droits admin.
- L'installer détecte automatiquement une installation existante et la met à
  jour en place (même dossier).
- `config.ini` et les données utilisateur (`data/`, `output/`, `templates/`)
  sont **préservés** à toute mise à jour.
- Les nouvelles clés de configuration requises par une montée de version sont
  ajoutées automatiquement (valeurs par défaut) sans toucher aux secrets
  existants.
- Le worker en cours est tué proprement avant copie des fichiers lors d'une MAJ.

**Non-Goals:**

- **Pas d'auto-update automatique** : aucune vérification en ligne, aucun
  téléchargement en arrière-plan. L'utilisateur lance l'installer lui-même.
- **Pas de Service Windows Session 0** : incompatible avec l'affichage des
  toasts et de l'icône tray (isolation Session 0 depuis Vista), et demanderait
  l'admin. Le worker reste un processus par-utilisateur en session interactive.
- **Pas de distribution macOS/Linux** pour le worker tray ni l'installer NSIS.
- **Pas de signature de code** dans cette itération (peut être ajouté
  ultérieurement).
- **Pas de gestion multi-utilisateurs** (cabinet mono-utilisateur par machine).

## Decisions

### D1 — Worker windowed vs tâche planifiée masquée

**Décision :** remplacer la tâche planifiée par un **second exécutable
`crm-tray.exe` compilé `console=False`**, démarré au logon via `HKCU\…\Run`,
contenant sa propre boucle scheduler et une icône tray.

*Justification :* `crm-server.exe` doit rester `console=True` (le handshake
stdout avec Tauri l'exige). Les alternatives pour masquer sa console lors d'un
lancement par `schtasks` (wrapper VBScript `WScript.Shell.Run …, 0`,
`CREATE_NO_WINDOW`, `powershell -WindowStyle Hidden`) sont fragiles : VBScript
peut être désactivé par politique d'entreprise, `WindowStyle Hidden` flash quand
même brièvement, et `CREATE_NO_WINDOW` ne s'applique pas au lancement par
`schtasks`. Un second exe windowed est la seule solution qui élimine la flash à
la source (le binaire lui-même n'a pas de console). Le coût (un spec PyInstaller
+ une ligne `externalBin`) est acceptable et isole proprement les
responsabilités : le sidecar sert l'API, le worker sert les rappels.

*Alternatives écartées :*
- **Vrai Service Windows (Session 0)** : rejeté car les toasts et l'icône tray
  sont impossibles en Session 0 (isolation depuis Vista) et l'install exigerait
  l'admin — les deux goals sont violés.
- **Garder `schtasks` + wrapper VBScript** : rejeté, fragilité WSH + ne résout
  pas le pilotage (pas de tray).

### D2 — Démarrage au logon via `HKCU\…\Run` (sans admin)

**Décision :** inscrire le worker dans
`HKCU\Software\Microsoft\Windows\CurrentVersion\Run` (valeur
`CabinetCRM-Tray`), plutôt que via une tâche planifiée ou un Service.

*Justification :* la clé `Run` HKCU est exécutée par Explorer au logon de
l'utilisateur, ne requiert **aucun droit administrateur** (contrairement à
`HKLM\…\Run`, aux Services, ou à `schtasks` avec élévation), et suffit pour le
cas mono-utilisateur. `crm/autostart.py` gère l'inscription idempotente et la
détection d'une valeur obsolète (chemin d'exe déplacé). Le code lit l'interval
depuis `meta.rappels_scheduler_interval` à chaque cycle → pas besoin de
réinstaller au changement d'interval.

### D3 — Singleton par mutex Win32 nommé + icône tray `pystray`

**Décision :** empêcher les multiples instances du worker via un **mutex Win32
nommé** `Local\tn.cabinet.gouiaaa.crm.tray` (préfixe `Local\` = limité à la
session). L'icône tray utilise `pystray` (dépendance légère, backend natif
Win32) avec menu « Ouvrir l'app / Statut / Quitter ».

*Justification :* sans singleton, chaque relance (logon + ouverture manuelle)
empilerait des icônes tray. Le mutex est le mécanisme Windows canonique pour ce
besoin ; il est conservé vivant jusqu'à la fermeture du process. `pystray` est
préféré à `infi.systray` ou à une implémentation `ctypes` maison pour sa
maturité et sa compatibilité PyInstaller (hiddenimports documentés). `Pillow`
(déjà en dépendance pour l'impression) fournit l'image de l'icône.

### D4 — Installer NSIS custom : détection registre + préservation config.ini

**Décision :** remplacer l'installer NSIS par défaut de Tauri par un template
`.nsi` custom (via `bundle.windows.nsis.installerHooks` ou un `.nsi` dédié) qui :

1. Lit une valeur **registre** `InstallPath` (posée au premier install) pour
   retrouver le dossier existant → réinstallation en place si présent, install
   fraîche sinon (chemin par défaut `%LOCALAPPDATA%\Cabinet CRM`).
2. **Tue tout `crm-tray.exe` et `crm-server.exe` en cours** avant la copie
   (hook `NSIS_HOOK_PREINSTALL`), pour libérer les fichiers verrouillés.
3. **Ne copie `config.ini` que s'il est absent** (préservation des secrets).
4. Pose le template `config.default.ini` (sans secrets) à chaque install
   (source de vérité pour les valeurs par défaut de migration).
5. Supprime la valeur `HKCU\…\Run\CabinetCRM-Tray` et lance le `cleanup` du
   worker à la désinstallation.

*Justification :* le modèle Tauri NSIS par défaut n'offre ni détection de
version, ni préservation sélective. La valeur `InstallPath` au registre est le
standard Windows pour les installers (lue aussi par le Panneau de configuration
« Ajouter/Supprimer des programmes »). Éviter d'écraser `config.ini` protège
les secrets irrécupérables (clés API).

*Alternative écartée :* fusionner `config.ini` côté NSIS (`nsis-ini` ou parsing
texte) — trop verbeux et fragile. La fusion est faite côté Python (cf. D5).

### D5 — Migration de configuration par script Python, versionnée comme le schéma DB

**Décision :** introduire un **numéro de version de config**
`CONFIG_VERSION` (entier) stocké en commentaire en tête de `config.ini` (ex.
`; config_version = 3`). Au démarrage, `crm/config_migrate.py` compare la
version du fichier à celle attendue par le code et, pour chaque version
manquante, **fusionne les clés** absentes depuis `config.default.ini` avec
leurs valeurs par défaut, sans modifier les clés déjà présentes. Le modèle
calque `SCHEMA_VERSION` / `_migrate()` de `crm/db.py` (snapshot pré-migration,
idempotence, garde anti-downgrade).

*Justification :* la fusion en Python (via `configparser`, déjà utilisé par
`src/config.py`) est fiable, testable unitairement, et garde la logique de
migration dans le code applicatif plutôt que dans l'installer (qui ne devrait
faire que de la copie de fichiers). `config.default.ini` devient la source de
vérité des clés/valeurs par défaut, embarquée à chaque release. Une clé
supprimée à une version n'est **jamais retirée** du fichier utilisateur (sécurité).

## Risks / Trade-offs

- **`pystray` + PyInstaller** : risque d'`ImportError` runtime si les
  hiddenimports (`pystray._win32`, `PIL`) sont oubliés. → *Mitigation :* spec
  `crm-tray.spec` déclare explicitement ces hiddenimports ; test du build
  frozen avant release.
- **Worker actif tant que l'utilisateur est loggé** (pas seulement quand l'app
  a tourné) → ~30-50 Mo RAM résident. → *Mitigation :* voulu (notif même si
  l'app n'est jamais ouverte) ; menu « Quitter » dans la tray pour l'arrêter.
- **Pas de notification avant le 1er logon post-boot** (le worker démarre au
  logon, pas au boot). → *Mitigation :* acceptable pour un cabinet
  mono-utilisateur ; documenté.
- **Mutex libéré si crash du worker** → une 2e instance peut démarrer au logon
  suivant. → *Mitigation :* idempotence de la boucle scheduler (seuls les
  rappels `planifie` sont traités) → pas de double-notification.
- **`config.ini` non présent à la première install** si l'utilisateur omet de le
  renseigner → certaines fonctionnalités (Mailjet, IA) indisponibles. →
  *Mitigation :* le template `config.default.ini` est posé automatiquement et
  l'app gère déjà l'absence de section (fallbacks dans `load_config`).
- **L'utilisateur peut « casser » le service en supprimant la valeur registre**
  (outils de nettoyage, msconfig). → *Mitigation :* `server.py` réinscrit
  l'autostart au démarrage de l'app (best-effort).
- **Migration de config qui échoue en lecture seule** (permissions dossier). →
  *Mitigation :* best-effort, journalisé dans `logs/service.log` ; l'app démarre
  quand même sur l'ancien `config.ini` (dégradation gracieuse).

## Migration Plan

1. **Build & release** : produire `crm-tray.exe` (`console=False`) à côté de
   `crm-server.exe` ; embarquer `config.default.ini` comme ressource ; générer
   l'installer NSIS custom.
2. **Sur un poste ayant l'ancienne version** (tâche `schtasks` présente) :
   l'installer la détecte et la supprime (`schtasks /Delete` best-effort via
   `cleanup_legacy_task`), puis installe le worker tray et inscrit le Run.
3. **`config.ini` existant préservé** ; au premier démarrage de la nouvelle
   version, `config_migrate.py` ajoute les nouvelles clés manquantes (ex. si une
   section `[rappels]` a été introduite) avec leurs valeurs par défaut.
4. **Vérification post-install** : icône tray présente, `crm-tray.exe` dans le
   gestionnaire des tâches, clé `HKCU\…\Run\CabinetCRM-Tray` posée, ancienne
   tâche `CabinetCRM-RappelsService` absente, un rappel échu déclenche un toast
   sans flash.
5. **Rollback** : en cas de problème, désinstallation propre (cleanup Run +
   worker), et réinstallation de l'ancien installer (qui recréera sa tâche
   `schtasks` via son propre `ensure_scheduled_task` au démarrage).

## Open Questions

- **Emplacement exact de `InstallPath` au registre** : `HKCU\Software\Cabinet
  CRM\InstallPath` vs `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\
  Cabinet CRM\InstallLocation`. *Résolu à l'implémentation* : on utilise une clé
  dédiée `HKCU\Software\Cabinet CRM` (InstallPath + InstallVersion), plus
  lisible et indépendante du mécanisme de désinstallation Tauri.
- **Signature de l'installer** : non inclus dans cette itération (cf. Non-Goals).
  Smartscreen affichera un avertissement au premier lancement. À traiter dans un
  changement ultérieur si besoin.
