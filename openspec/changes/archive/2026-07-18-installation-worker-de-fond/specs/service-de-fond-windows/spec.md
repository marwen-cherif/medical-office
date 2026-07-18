## ADDED Requirements

### Requirement: Exécution transparente sans fenêtre console

Le service de fond SHALL s'exécuter **sans jamais afficher de fenêtre console**,
que ce soit au démarrage, à chaque cycle de traitement, ou lors de l'émission
d'une notification. L'exécutable dédié (`crm-tray.exe`) SHALL être compilé en
mode windowed (`console=False` à la build PyInstaller). Le sous-processus
PowerShell émetteur de toasts SHALL être lancé avec
`creationflags=CREATE_NO_WINDOW` (0x08000000) pour éviter toute flash.

#### Scenario: Démarrage du worker au logon sans flash

- **WHEN** l'utilisateur ouvre sa session Windows et que le worker `crm-tray.exe`
  démarre via la clé `HKCU\…\Run`
- **THEN** aucune fenêtre console ne s'affiche à l'écran, à aucun moment du
  démarrage

#### Scenario: Notification toast sans flash

- **WHEN** le worker émet une notification toast pour un rappel échu via le
  sous-processus PowerShell
- **THEN** le `powershell.exe` enfant est lancé avec `CREATE_NO_WINDOW` et aucune
  console noire n'apparaît

### Requirement: Démarrage automatique au logon sans administrateur

Le système SHALL inscrire le worker de fond dans la clé registre
`HKCU\Software\Microsoft\Windows\CurrentVersion\Run` (valeur `CabinetCRM-Tray`)
pour qu'il démarre automatiquement à la connexion de l'utilisateur. Cette
inscription SHALL NOT nécessiter de droits administrateur (HKCU est
par-utilisateur). L'inscription SHALL être idempotente et le système SHALL
détecter une valeur obsolète (chemin d'exe déplacé) pour la réinscrire.

#### Scenario: Inscription automatique au démarrage de l'app

- **WHEN** l'application démarre et qu'aucune valeur `CabinetCRM-Tray` n'est
  présente dans `HKCU\…\Run` (ou qu'elle pointe vers un chemin obsolète)
- **THEN** le système inscrit le chemin de `crm-tray.exe` dans cette clé
- **AND** l'opération ne déclenche aucune invite d'élévation (pas d'UAC)

#### Scenario: Premier cycle de traitement dès le logon

- **WHEN** l'utilisateur ouvre sa session et que le worker démarre
- **THEN** un premier cycle de traitement des rappels échus s'exécute
  immédiatement (rattrapage des rappels en retard depuis le dernier arrêt)
- **AND** les cycles suivants s'exécutent toutes les
  `rappels_scheduler_interval` minutes

### Requirement: Boucle scheduler interne pilotée par paramètre

Le worker de fond SHALL contenir sa propre boucle de planification (thread
daemon) qui appelle le cycle de traitement des rappels à intervalle régulier.
L'intervalle SHALL être relu depuis `meta.rappels_scheduler_interval` à chaque
cycle, de sorte qu'un changement de paramétrage via l'UI soit pris en compte
sans redémarrage du worker. La boucle SHALL pouvoir être arrêtée proprement et
immédiatement (arrêt non bloquant pendant la phase d'attente).

#### Scenario: Changement d'intervalle pris en compte sans redémarrage

- **WHEN** l'utilisateur modifie `rappels_scheduler_interval` via l'écran de
  paramétrage pendant que le worker tourne
- **THEN** le cycle suivant du worker utilise le nouvel intervalle lu depuis la
  base
- **AND** aucune réinstallation ni redémarrage du worker n'est nécessaire

#### Scenario: Survie aux erreurs de cycle

- **WHEN** un cycle de traitement lève une exception (base inaccessible,
  erreur de notification)
- **THEN** l'exception est journalisée et le thread scheduler ne s'arrête pas
- **AND** le cycle suivant s'exécute normalement à l'intervalle prévu

### Requirement: Icône tray pilotable

Le worker de fond SHALL poser une icône dans la zone de notification Windows,
accompagnée d'un menu contextuel permettant à l'utilisateur de : ouvrir
l'application principale, consulter le statut du service (dernier cycle, nombre
de rappels traités, prochain check), et quitter le service de fond. Le
double-clic sur l'icône SHALL ouvrir l'application.

#### Scenario: Quitter le service depuis la tray

- **WHEN** l'utilisateur clique sur « Quitter le service » dans le menu de
  l'icône tray
- **THEN** le thread scheduler s'arrête proprement, l'icône disparaît de la
  zone de notification, et le processus se termine
- **AND** la clé `HKCU\…\Run` reste en place (le service redémarrera au prochain
  logon)

#### Scenario: Ouvrir l'application depuis la tray

- **WHEN** l'utilisateur double-clique sur l'icône tray (ou choisit « Ouvrir
  Cabinet CRM »)
- **THEN** l'exécutable Tauri principal est lancé en mode détaché, sans fenêtre
  console additionnelle

### Requirement: Singleton du worker par session

Le système SHALL garantir qu'au plus une instance du worker de fond tourne par
session utilisateur, via un mutex Win32 nommé (`Local\tn.cabinet.gouiaaa.crm.tray`).
Si le mutex existe déjà, le second lancement SHALL se terminer immédiatement et
silencieusement sans poser de seconde icône tray.

#### Scenario: Second lancement bloqué

- **WHEN** le worker est déjà en cours d'exécution et qu'un second lancement est
  déclenché (ex. l'utilisateur ouvre l'app qui tente de démarrer le worker)
- **THEN** le second processus détecte le mutex existant et se termine
  immédiatement avec un code de sortie de succès
- **AND** aucune icône tray supplémentaire n'apparaît

### Requirement: Migration depuis l'ancienne tâche planifiée

Le système SHALL supprimer, de façon best-effort, l'ancienne tâche planifiée
`CabinetCRM-RappelsService` (`schtasks`) lorsqu'il installe ou démarre le worker
tray, afin d'éviter deux mécanismes concurrents de déclenchement des rappels.
Cette suppression SHALL être idempotente (silencieuse si la tâche est déjà
absente) et ne pas faire échouer le démarrage en cas d'erreur.

#### Scenario: Nettoyage automatique de l'ancienne tâche

- **WHEN** le worker tray démarre sur un poste qui possédait l'ancienne version
  (tâche `CabinetCRM-RappelsService` encore présente)
- **THEN** le système supprime cette tâche via `schtasks /Delete /F`
- **AND** aucun message d'erreur n'est remonté à l'utilisateur si la suppression
  échoue (journalisation seulement)

### Requirement: Notifications Windows en session interactive

Le worker de fond SHALL émettre les notifications toast depuis la session
interactive de l'utilisateur (et non depuis une Session 0 de type Service
Windows), afin qu'elles s'affichent dans le Centre de notifications et
persistent après la fin du processus émetteur. L'AUMID utilisée (`tn.cabinet.gouiaaa.crm`,
identifier Tauri de l'app) SHALL être déclarée dans
`HKCU\Software\Classes\AppUserModelId\…` avant émission.

#### Scenario: Toast persistant après fin du worker

- **WHEN** un rappel échu déclenche un toast et que le worker se termine peu
  après (ex. l'utilisateur clique « Quitter »)
- **THEN** le toast reste visible dans le Centre de notifications Windows
- **AND** il est rattaché à l'application Cabinet CRM via son AUMID

### Requirement: Journalisation du service de fond

Le worker de fond SHALL journaliser son activité (démarrage, cycles, erreurs,
notifications) dans un fichier rotatif `logs/service.log` à côté de la base de
données, réutilisant la configuration de journalisation du module de service.
Aucune erreur de journalisation ne SHALL bloquer le démarrage du worker
(dégradation gracieuse vers `logging.basicConfig`).

#### Scenario: Cycle erroné tracé dans le log

- **WHEN** un cycle de traitement échoue (exception capturée)
- **THEN** l'erreur est écrite dans `logs/service.log` avec sa trace complète
  (`exc_info=True`)
- **AND** le worker continue de fonctionner
