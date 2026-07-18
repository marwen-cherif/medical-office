# Capability: Installation & Mise à jour

## Purpose
Gérer le cycle de vie de l'application Cabinet CRM via un installateur NSIS pour utilisateur sans élévation de privilèges (CurrentUser), prenant en charge la détection d'installations antérieures, les mises à jour en place en arrêtant proprement les processus, et les migrations de configuration.

## Requirements

### Requirement: Détection automatique de l'installation existante

L'installer NSIS SHALL détecter une installation préexistante de l'application
en lisant la valeur `InstallPath` depuis la clé registre
`HKCU\Software\Cabinet CRM` posée lors de la première installation. Si une
installation est détectée, l'installer SHALL proposer une **mise à jour en place**
(dossier existant, sans perte de données). Si aucune installation n'est
détectée, l'installer SHALL procéder à une **installation fraîche** dans le
dossier par défaut (`%LOCALAPPDATA%\Cabinet CRM`). Le dossier détecté SHALL être
affiché à l'utilisateur pour confirmation avant la copie.

#### Scenario: Mise à jour d'une installation existante

- **WHEN** l'utilisateur lance l'installer et qu'une valeur `InstallPath` est
  présente dans `HKCU\Software\Cabinet CRM`
- **THEN** l'installer affiche le dossier existant détecté et propose la mise à
  jour en place
- **AND** les données utilisateur (`data/`, `output/`, `templates/`,
    `config.ini`) sont préservées

#### Scenario: Installation fraîche

- **WHEN** l'utilisateur lance l'installer et qu'aucune valeur `InstallPath`
  n'est présente au registre
- **THEN** l'installer propose le dossier par défaut `%LOCALAPPDATA%\Cabinet CRM`
  et procède à une installation complète

### Requirement: Installation sans droits administrateur

L'installer SHALL s'exécuter en mode `currentUser` (installation par
utilisateur, dans `%LOCALAPPDATA%`) et SHALL NOT nécessiter de droits
administrateur ni déclencher d'invite d'élévation UAC. Toutes les écritures
registre (clé `HKCU\Software\Cabinet CRM`, clé `HKCU\…\Run` pour le worker) et
fichiers se font dans les espaces par-utilisateur.

#### Scenario: Installation par un utilisateur non-administrateur

- **WHEN** un utilisateur sans droits administrateur lance l'installer
- **THEN** l'installation se déroule intégralement sans invite UAC et sans
  échec lié aux permissions
- **AND** l'application est utilisable immédiatement pour cet utilisateur

### Requirement: Arrêt du worker avant mise à jour

L'installer SHALL arrêter tout processus `crm-tray.exe` et tout processus
`Cabinet CRM.exe` (application principale) en cours d'exécution **avant** la
copie des fichiers, afin de libérer les exécutables verrouillés. Cette étape
SHALL s'exécuter dans le hook de pré-installation NSIS et SHALL se terminer
avant la phase de copie, sans quoi la mise à jour des fichiers échouerait.

#### Scenario: Worker en cours arrêté avant copie

- **WHEN** l'utilisateur lance une mise à jour alors que `crm-tray.exe` tourne
  en arrière-plan
- **THEN** l'installer termine ce processus (`taskkill`) avant de copier le
  nouveau `crm-tray.exe`
- **AND** aucune erreur « fichier en cours d'utilisation » n'est levée

### Requirement: Préservation des secrets et données utilisateur

L'installer SHALL préserver l'intégralité des données utilisateur à toute mise
à jour : le fichier `config.ini` (qui contient les clés Mailjet et API IA), le
dossier `data/` (base SQLite `cabinet.db` et backups), le dossier `output/`
(documents générés) et le dossier `templates/`. L'installer SHALL NOT écraser
un `config.ini` existant, même si un template est embarqué dans l'installer.

#### Scenario: config.ini préservé à la mise à jour

- **WHEN** l'utilisateur met à jour l'application alors qu'un `config.ini`
  renseigné (avec ses clés Mailjet et API IA) existe dans le dossier
  d'installation
- **THEN** l'installer ne modifie pas ce `config.ini`
- **AND** les clés et valeurs existantes (y compris les secrets) sont
    strictement identiques après la mise à jour

#### Scenario: Template posé à la première installation

- **WHEN** l'installation est fraîche (aucun `config.ini` existant)
- **THEN** l'installer copie `config.default.ini` (sans secrets, valeurs par
  défaut) en tant que `config.ini`
- **AND** l'utilisateur peut ensuite renseigner ses clés dans ce fichier

### Requirement: Migration versionnée de la configuration

Le système SHALL maintenir un numéro de version de configuration
(`config_version`, entier) en commentaire en tête de `config.ini`. Au
démarrage de l'application, si la version du fichier est inférieure à celle
attendue par le code, un script de migration SHALL fusionner les nouvelles
clés requises depuis `config.default.ini` vers le `config.ini` existant, en
n'ajoutant que les clés absentes **sans modifier aucune valeur déjà
renseignée**. La migration SHALL être idempotente, journalisée, et prendre un
snapshot pré-migration (`config.pre-v<N>.ini`) avant toute modification. Une
clé supprimée à une version supérieure SHALL NOT être retirée du fichier
utilisateur.

#### Scenario: Ajout de nouvelles clés à la mise à jour

- **WHEN** l'application démarre après une mise à jour qui introduit une
  nouvelle section/clé de configuration absente du `config.ini` existant
- **THEN** la migration ajoute cette clé avec sa valeur par défaut issue de
  `config.default.ini`
- **AND** les clés et valeurs déjà présentes (dont les secrets) sont
    inchangées

#### Scenario: Idempotence de la migration

- **WHEN** l'application démarre deux fois de suite sans changement de version
  de configuration
- **THEN** la deuxième exécution ne modifie pas `config.ini`
- **AND** aucun snapshot pré-migration n'est créé la deuxième fois

### Requirement: Enregistrement de la version installée

L'installer SHALL écrire la version de l'application (`InstallVersion`) aux
côtés du chemin (`InstallPath`) dans `HKCU\Software\Cabinet CRM`. Cette valeur
SHALL permettre à l'installer comme à l'application de déterminer la version
précédemment installée (utile pour décider d'une migration de configuration ou
d'un nettoyage de l'ancienne tâche planifiée).

#### Scenario: Version lue par l'installer pour décision de migration

- **WHEN** l'installer détecte une `InstallVersion` antérieure à la version
  introduisant le worker tray
- **THEN** il sait qu'un nettoyage de l'ancienne tâche `schtasks` est nécessaire
  au prochain démarrage de l'app
- **AND** il peut adapter les étapes de migration en conséquence

### Requirement: Désinstallation propre

L'installer SHALL, à la désinstallation, supprimer la valeur
`CabinetCRM-Tray` de la clé `HKCU\…\Run` (pour empêcher le worker de redémarrer
au prochain logon), arrêter tout worker en cours, et retirer la clé
`HKCU\Software\Cabinet CRM`. Le désinstalleur SHALL préserver les données
utilisateur (`config.ini`, `data/`, `output/`, `templates/`) par défaut, sauf
demande explicite de l'utilisateur.

#### Scenario: Désinstallation sans perte de données

- **WHEN** l'utilisateur désinstalle l'application
- **THEN** le worker est arrêté et la valeur `HKCU\…\Run\CabinetCRM-Tray` est
  supprimée
- **AND** les dossiers `data/`, `output/`, `templates/` et le fichier
    `config.ini` sont conservés (l'utilisateur peut réinstaller sans perte)
