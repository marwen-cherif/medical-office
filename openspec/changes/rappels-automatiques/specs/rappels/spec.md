## ADDED Requirements

### Requirement: Création d'un rappel

Le système SHALL permettre de créer un rappel daté, comportant au minimum une date
d'échéance, un type (`alerte_interne` ou `message_patient`) et un libellé/texte. Un
rappel MAY être rattaché à un patient et/ou à un document existant. Pour un rappel de
type `message_patient`, le canal SHALL être WhatsApp assisté et le système SHALL exiger
un texte de message destiné au patient ainsi qu'un patient rattaché disposant d'un numéro
de téléphone exploitable.

#### Scenario: Créer une alerte interne autonome

- **WHEN** le praticien crée un rappel de type `alerte_interne` avec une date d'échéance
  future et un libellé
- **THEN** le système enregistre le rappel avec l'état `planifie` et l'affiche dans la
  liste des rappels à venir

#### Scenario: Créer un message patient WhatsApp

- **WHEN** le praticien crée un rappel de type `message_patient`, rattaché à un patient
  possédant un numéro de téléphone, avec un texte et une date d'échéance future
- **THEN** le système enregistre le rappel à l'état `planifie` avec le texte saisi et le
  canal WhatsApp assisté

#### Scenario: Refus d'un message patient sans numéro exploitable

- **WHEN** le praticien crée un rappel `message_patient` pour un patient sans numéro de
  téléphone exploitable
- **THEN** le système refuse l'enregistrement et signale que le patient n'a pas de numéro
  utilisable pour WhatsApp

### Requirement: Planification depuis l'envoi d'un document

Le système SHALL permettre, après la génération/envoi d'un document pour un patient, de
créer un rappel pré-rempli rattaché à ce patient et à ce document, en proposant une
échéance relative (par exemple +1 mois, +2 mois).

#### Scenario: Planifier un rappel après envoi d'une note d'honoraires

- **WHEN** le praticien vient d'envoyer une note d'honoraires à un patient et choisit
  « Planifier un rappel »
- **THEN** le système ouvre la création d'un rappel pré-rempli avec le patient et le
  document rattachés, et une échéance par défaut calculée à partir de la date du jour

### Requirement: Déclenchement des rappels échus, application fermée

Le système SHALL traiter les rappels arrivés à échéance même lorsque l'application
graphique est fermée, au moyen d'un processus de fond exécuté périodiquement par une
tâche planifiée Windows. À l'échéance, le processus SHALL notifier le praticien
(notification Windows) et mettre les rappels dus en file ; il ne SHALL PAS envoyer
lui-même de message au patient. Le traitement SHALL être idempotent : un rappel déjà mis
en file ou traité ne SHALL pas être re-notifié en boucle.

#### Scenario: Message WhatsApp mis en file et notifié à l'échéance, app fermée

- **WHEN** la tâche planifiée s'exécute et trouve un rappel `message_patient` dont
  l'échéance est dépassée et l'état est `planifie`
- **THEN** le système fait passer le rappel à l'état `a_envoyer`, le place dans la file
  WhatsApp et émet une notification Windows informant le praticien qu'un rappel est à
  envoyer

#### Scenario: Alerte interne notifiée à l'échéance, app fermée

- **WHEN** la tâche planifiée s'exécute et trouve une alerte interne échue à l'état
  `planifie`
- **THEN** le système fait passer l'alerte à l'état `du` et émet une notification Windows
  pour le praticien

#### Scenario: Pas de notification répétée

- **WHEN** la tâche planifiée s'exécute plusieurs fois alors qu'un rappel est déjà à
  l'état `a_envoyer`, `du`, `envoye` ou `traite`
- **THEN** le système ne re-notifie pas ce rappel et ne crée aucun doublon en file

### Requirement: File WhatsApp assistée et envoi en un clic

Le système SHALL présenter dans l'application la file des messages patients dus
(`a_envoyer`) et SHALL permettre au praticien d'en envoyer un en un clic via WhatsApp,
avec le texte pré-rempli (lien `wa.me` construit à partir du numéro du patient normalisé
au format international). Le système ne SHALL PAS envoyer le message WhatsApp
automatiquement.

#### Scenario: Envoi assisté en un clic

- **WHEN** le praticien sélectionne « Envoyer via WhatsApp » sur un rappel de la file
- **THEN** le système ouvre WhatsApp avec le numéro du patient et le texte pré-rempli,
  puis permet de marquer le rappel comme `envoye`

#### Scenario: Numéro invalide signalé

- **WHEN** le praticien tente l'envoi assisté sur un rappel dont le numéro patient ne peut
  pas être normalisé en format international valide
- **THEN** le système signale le problème et n'ouvre pas de lien `wa.me` erroné

### Requirement: Présentation des rappels dus au démarrage

Au démarrage de l'application, le système SHALL présenter au praticien les rappels échus
qui requièrent son attention : les alertes internes dues et les messages WhatsApp en file
d'attente.

#### Scenario: Rappels dus affichés à l'ouverture

- **WHEN** le praticien ouvre l'application et qu'au moins un rappel est dû (alerte
  interne `du` ou message WhatsApp `a_envoyer`)
- **THEN** le système affiche ces rappels en évidence afin qu'il puisse agir (envoyer via
  WhatsApp ou marquer traité)

### Requirement: Gestion du cycle de vie d'un rappel

Le système SHALL permettre de lister les rappels filtrés par état (à venir, dus, traités),
de les modifier tant qu'ils ne sont pas envoyés/traités, et de les annuler. L'annulation
SHALL empêcher toute mise en file ou notification ultérieure.

#### Scenario: Annuler un rappel planifié

- **WHEN** le praticien annule un rappel à l'état `planifie`
- **THEN** le système fait passer le rappel à l'état `annule` et la tâche planifiée ne le
  met jamais en file ni ne le notifie

#### Scenario: Marquer une alerte interne comme traitée

- **WHEN** le praticien marque une alerte interne due comme traitée
- **THEN** le système fait passer le rappel à l'état `traite` et ne le présente plus parmi
  les rappels dus
