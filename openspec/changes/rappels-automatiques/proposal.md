## Why

Aujourd'hui, une fois une note d'honoraires (ou tout autre document) envoyée à un
patient, le cabinet n'a aucun moyen de planifier un suivi. Le praticien doit se souvenir
de tête de rappeler un patient « un mois après » ou de préparer un message de relance, et
ne peut pas programmer à l'avance un message destiné au patient (par exemple un rappel de
contrôle à +2 mois). Ces oublis coûtent des rendez-vous de suivi.

L'objectif est de pouvoir, au moment où l'on envoie un document — ou à tout moment —
**planifier un rappel daté** : soit une **alerte interne** pour le praticien, soit un
**message au patient via WhatsApp**, rédigé à l'avance et présenté à l'échéance pour
envoi en un clic, le praticien étant notifié à temps même si l'application est fermée.

## What Changes

- **Nouveau concept « Rappel »** : un rappel daté, optionnellement rattaché à un patient
  et/ou à un document, avec une date d'échéance.
- **Deux types de rappels** :
  - **Alerte interne** : à l'échéance, le praticien est notifié (« le patient X devait
    revenir »). Aucun message ne part vers le patient.
  - **Message patient planifié (WhatsApp)** : un texte libre, rédigé à l'avance par le
    praticien, destiné au patient à une date future.
- **Canal patient : WhatsApp assisté (lien `wa.me`) uniquement.** Texte 100 % libre. À
  l'échéance, le message est mis en file et l'application propose de l'envoyer en **un
  clic** (ouverture de WhatsApp avec le texte pré-rempli vers le numéro du patient).
  - *Pas d'email / Mailjet* pour les messages patients (hors périmètre).
  - *Pas d'envoi WhatsApp 100 % automatique* : contrainte Meta — hors de la fenêtre de
    24 h, seul un modèle pré-approuvé est autorisé, pas de texte libre. L'envoi assisté en
    un clic est donc la seule voie compatible avec un texte libre. L'intégration WhatsApp
    Business API par modèles approuvés est documentée comme évolution future.
- **Déclenchement par service de fond Windows** : une tâche planifiée Windows exécute
  périodiquement le moteur de rappels en mode sans interface afin, à l'échéance et même
  application fermée, de **notifier** le praticien (notification Windows) et de **mettre
  en file** les rappels dus (alertes internes + messages WhatsApp à envoyer).
- **Planification depuis l'envoi d'un document** : après génération/envoi d'une note, le
  praticien peut créer un rappel pré-rempli (patient + document rattachés).
- **Gestion des rappels dans le CRM** : liste des rappels (à venir, dus, traités),
  création/édition/annulation, présentation des rappels échus au démarrage, et action
  « Envoyer via WhatsApp » sur la file.

## Capabilities

### New Capabilities

- `rappels`: planification, stockage, présentation et déclenchement des rappels (alertes
  internes et messages patients WhatsApp planifiés), incluant la file d'envoi WhatsApp
  assisté en un clic et le déclenchement/notification par service de fond Windows.

### Modified Capabilities

<!-- Aucune capacité existante n'a de spec dans openspec/specs/ ; pas de modification de
     requirements existants. -->

## Impact

- **Schéma SQLite (`crm/db.py`)** : nouvelle table `rappels` via
  `CREATE TABLE IF NOT EXISTS`, bump de `SCHEMA_VERSION` + étape `_migrate()` idempotente,
  snapshot pré-migration (règles de préservation des données, voir CLAUDE.md). Additif
  uniquement, aucune donnée existante touchée.
- **`crm/repo.py`** : dataclass `Rappel` + CRUD (création, liste filtrée par état,
  marquage en file / envoyé / annulé / traité).
- **`crm/`** : nouveau module de planification/déclenchement des rappels (lecture des
  rappels dus, mise en file, construction du lien `wa.me`) et un point d'entrée « mode
  service » sans interface (sans Flet ni Word) pour la tâche planifiée.
- **`crm/app.py`** : nouvel écran/section « Rappels » (liste + création), bouton
  « Planifier un rappel » après envoi d'un document, présentation des rappels dus au
  démarrage, action « Envoyer via WhatsApp » (ouverture `wa.me`) pour la file.
- **Moteur partagé (`src/`)** : non modifié ; cette fonctionnalité n'utilise pas
  `src/mailer.py` (pas d'email).
- **Déploiement** : installation/maj d'une **tâche planifiée Windows** appelant l'exe en
  mode service ; documentation du build (`build-crm.bat`, specs PyInstaller) et du
  paramétrage (intervalle, activation).
- **`config.ini`** : éventuels paramètres (activation du service, intervalle de
  vérification).
