# rappels

## Purpose

Permettre de planifier des rappels datés (alertes internes pour le praticien ou messages à envoyer au patient via WhatsApp assisté `wa.me`) rattachés ou non à des patients et des documents, avec déclenchement automatique par tâche planifiée Windows, notification système Windows 11 configurable, et accès centralisé via une icône cloche persistante dans l'interface React.

Le canal `wa.me` (envoi assisté, texte libre) est **toujours disponible** et ne dépend
d'aucun feature flag. Le feature flag `whatsapp_api_enabled` (Meta Cloud API) concerne
uniquement l'envoi de documents via templates et n'a aucun impact sur les rappels.

**Cycle de vie complet d'un rappel :**
- `planifie` → (à l'échéance, tâche planifiée) → `du` (alerte interne) ou `a_envoyer` (message patient)
- `a_envoyer` → (ignoré depuis la cloche sans envoi) → `lu`
- `a_envoyer` / `lu` → (envoi `wa.me` confirmé) → `envoye`
- `du` → (marqué traité) → `traite`
- `envoye` → (marqué traité) → `traite`
- `planifie` → (annulation manuelle) → `annule`

La table `rappels` porte une colonne `lu` (booléen, défaut `0`). Les rappels `lu` sont
hors du badge et du panneau cloche mais restent accessibles et envoyables depuis la liste
complète. Les settings rappels (notifications activées, intervalle tâche, indicatif pays)
sont stockés dans la table `meta` et configurables via le Paramétrage UI.

## Requirements

### Requirement: Création d'un rappel

Le système SHALL permettre de créer un rappel daté, comportant au minimum une date
d'échéance, un type (`alerte_interne` ou `message_patient`) et un libellé/texte. Un
rappel MAY être rattaché à un patient et/ou à un document existant. Pour un rappel de
type `message_patient`, le canal SHALL être WhatsApp assisté (`wa.me`) et le système
SHALL exiger un texte de message destiné au patient ainsi qu'un patient rattaché
disposant d'au moins un numéro marqué `is_whatsapp = 1` dans `patient_phones`. Le
système SHALL utiliser le premier numéro `is_whatsapp = 1` du patient pour construire
le lien `wa.me` ; si aucun numéro marqué WhatsApp n'existe, la création est refusée.
La création d'un rappel SHALL être possible depuis plusieurs points d'entrée : la section
dédiée, la fiche patient (onglet Rappels), et après l'envoi d'un document.

#### Scenario: Créer une alerte interne autonome

- **WHEN** le praticien crée un rappel de type `alerte_interne` avec une date d'échéance
  future et un libellé
- **THEN** le système enregistre le rappel avec l'état `planifie` et l'affiche dans la
  liste des rappels à venir

#### Scenario: Créer un message patient WhatsApp

- **WHEN** le praticien crée un rappel de type `message_patient`, rattaché à un patient
  possédant au moins un numéro marqué `is_whatsapp = 1` dans `patient_phones`, avec un
  texte et une date d'échéance future
- **THEN** le système enregistre le rappel à l'état `planifie` avec le texte saisi et le
  canal WhatsApp assisté (`wa.me`)

#### Scenario: Refus d'un message patient sans numéro exploitable

- **WHEN** le praticien crée un rappel `message_patient` pour un patient sans aucun
  numéro dans `patient_phones`
- **THEN** le système refuse l'enregistrement et signale que le patient n'a pas de numéro
  utilisable pour WhatsApp

#### Scenario: Refus d'un message patient sans numéro WhatsApp marqué

- **WHEN** le praticien crée un rappel `message_patient` pour un patient dont aucun
  numéro dans `patient_phones` n'est marqué `is_whatsapp = 1`
- **THEN** le système refuse l'enregistrement et signale que le patient n'a pas de
  numéro WhatsApp utilisable (distinct du cas « pas de numéro du tout »)

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
graphique (frontend React/Tauri) est fermée, au moyen d'un processus de fond headless
distinct du serveur FastAPI (`crm_server.py`), exécuté périodiquement par une tâche
planifiée Windows. Ce processus headless SHALL réutiliser `crm/db.py` et `crm/repo.py`
sans démarrer Uvicorn ni l'interface web. À l'échéance, le processus SHALL mettre les
rappels dus en file et, si les notifications Windows sont activées dans le Paramétrage,
émettre une notification Windows 11 native par rappel échu. Il ne SHALL PAS envoyer
lui-même de message au patient. Le traitement SHALL être idempotent : un rappel déjà
mis en file ou traité ne SHALL pas être re-notifié en boucle.

#### Scenario: Message WhatsApp mis en file et notifié à l'échéance, app fermée

- **WHEN** la tâche planifiée s'exécute et trouve un rappel `message_patient` dont
  l'échéance est dépassée et l'état est `planifie`
- **THEN** le système fait passer le rappel à l'état `a_envoyer`, le place dans la file
  et, si les notifications sont activées, émet une notification Windows 11 informant le
  praticien qu'un rappel est à envoyer

#### Scenario: Alerte interne notifiée à l'échéance, app fermée

- **WHEN** la tâche planifiée s'exécute et trouve une alerte interne échue à l'état
  `planifie`
- **THEN** le système fait passer l'alerte à l'état `du` et, si les notifications sont
  activées, émet une notification Windows 11 pour le praticien

#### Scenario: Rattrapage après poste éteint — N notifications individuelles

- **WHEN** le poste redémarre ou la tâche planifiée s'exécute après une interruption et
  trouve N rappels dont l'échéance est dépassée
- **THEN** le système traite chaque rappel individuellement et émet une notification
  Windows 11 distincte par rappel échu (N notifications individuelles)

#### Scenario: Pas de re-notification d'un rappel déjà traité

- **WHEN** la tâche planifiée s'exécute plusieurs fois alors qu'un rappel est déjà à
  l'état `a_envoyer`, `lu`, `du`, `envoye` ou `traite`
- **THEN** le système ne re-notifie pas ce rappel et ne crée aucun doublon en file

#### Scenario: Notifications désactivées dans le Paramétrage

- **WHEN** le praticien a désactivé les notifications Windows dans le Paramétrage et
  que la tâche planifiée s'exécute à l'échéance d'un rappel
- **THEN** le système met le rappel en file (`a_envoyer` ou `du`) sans émettre aucune
  notification Windows ; le rappel reste visible dans la cloche à l'ouverture de l'app

### Requirement: Icône cloche et centre de notifications rappels

Le système SHALL afficher une icône cloche persistante dans la barre de navigation
principale de l'interface React, visible depuis tous les écrans. La cloche SHALL
afficher un badge numérique indiquant le nombre de rappels actifs non traités (`du` +
`a_envoyer` non lus). En cliquant sur la cloche, le praticien accède à un panneau
listant ces rappels, chacun proposant trois actions :

- **Ignorer (discard)** : un rappel `alerte_interne` passe à `traite` ; un
  `message_patient` passe à `lu` — dans les deux cas le badge se décrémente et le rappel
  quitte le panneau
- **Ouvrir la fiche patient** : navigue vers la fiche du patient rattaché (clic sur le
  nom) ; disponible uniquement si le rappel est rattaché à un patient
- **Envoyer via WhatsApp** : ouvre le lien `wa.me` avec le texte du rappel pré-rempli ;
  si le patient a un seul numéro `is_whatsapp = 1`, le lien s'ouvre directement ; si le
  patient en a plusieurs, un sélecteur de numéro est proposé avant l'ouverture ;
  disponible uniquement pour les rappels `message_patient`

#### Scenario: Badge cloche mis à jour en temps réel

- **WHEN** un nouveau rappel passe à l'état `du` ou `a_envoyer`
- **THEN** le badge de la cloche se met à jour sans rechargement complet de la page

#### Scenario: Ignorer un rappel depuis la cloche

- **WHEN** le praticien clique « Ignorer » sur un rappel dans le panneau de la cloche
- **THEN** le rappel disparaît du panneau et le badge se décrémente ; un rappel
  `alerte_interne` passe à `traite`, un `message_patient` passe à `lu` (reste accessible
  et envoyable depuis la liste complète)

#### Scenario: Ouvrir la fiche patient depuis la cloche

- **WHEN** le praticien clique sur le nom du patient dans un rappel du panneau
- **THEN** l'interface navigue vers la fiche patient correspondante

#### Scenario: Envoyer WhatsApp depuis la cloche — sélecteur si plusieurs numéros

- **WHEN** le praticien clique « Envoyer via WhatsApp » sur un rappel `message_patient`
  et que le patient a plusieurs numéros `is_whatsapp = 1`
- **THEN** le système affiche un sélecteur de numéro (nom + numéro normalisé), puis
  ouvre le lien `wa.me` avec le numéro choisi et le texte du rappel pré-rempli

#### Scenario: Envoyer WhatsApp depuis la cloche — direct si un seul numéro

- **WHEN** le praticien clique « Envoyer via WhatsApp » sur un rappel `message_patient`
  et que le patient n'a qu'un seul numéro `is_whatsapp = 1`
- **THEN** le système ouvre directement le lien `wa.me` sans sélecteur intermédiaire

### Requirement: Onglet Rappels sur la fiche patient

Le système SHALL exposer un onglet « Rappels » sur la fiche patient, affichant tous les
rappels rattachés à ce patient (tous états confondus), filtrables par état (à venir /
dus / lus / traités / annulés). Depuis cet onglet, le praticien SHALL pouvoir créer un
nouveau rappel pré-rempli avec ce patient, modifier un rappel existant (si son état le
permet), et annuler un rappel planifié.

#### Scenario: Rappels d'un patient visibles sur sa fiche

- **WHEN** le praticien ouvre la fiche d'un patient et navigue vers l'onglet « Rappels »
- **THEN** le système affiche la liste de tous les rappels rattachés à ce patient, triés
  par échéance décroissante, avec état, type, libellé et document rattaché le cas échéant

#### Scenario: Créer un rappel depuis la fiche patient

- **WHEN** le praticien clique « Nouveau rappel » dans l'onglet Rappels de la fiche
- **THEN** le formulaire de création s'ouvre pré-rempli avec ce patient comme destinataire

### Requirement: File WhatsApp assistée et envoi en un clic

Le système SHALL présenter dans l'interface React les rappels patients dus
(`a_envoyer` et `lu`) et SHALL permettre au praticien d'en envoyer un via WhatsApp
assisté — lien `wa.me` construit à partir du numéro `is_whatsapp = 1` sélectionné (ou
le seul disponible) du patient normalisé au format international (indicatif pays par
défaut `+216`, configurable dans le Paramétrage). Ce canal (`wa.me`) est **indépendant
du feature flag `whatsapp_api_enabled`** et reste fonctionnel même si la Meta Cloud API
est désactivée.

#### Scenario: Envoi assisté depuis la liste

- **WHEN** le praticien sélectionne « Envoyer via WhatsApp » sur un rappel `a_envoyer`
  ou `lu` dans la liste
- **THEN** le système ouvre le lien `wa.me` avec le numéro sélectionné et le texte
  pré-rempli, puis marque le rappel `envoye` après confirmation du praticien

#### Scenario: Numéro invalide signalé

- **WHEN** le praticien tente l'envoi assisté sur un rappel dont le numéro patient ne
  peut pas être normalisé en format international valide
- **THEN** le système signale le problème et n'ouvre pas de lien `wa.me` erroné

### Requirement: Présentation des rappels dus au démarrage

Au démarrage de l'application (chargement initial du frontend React), le système SHALL
interroger le backend FastAPI et initialiser le badge de la cloche avec le nombre de
rappels actifs. Ce mécanisme constitue également un filet de sécurité si la tâche
planifiée Windows est absente ou désactivée.

#### Scenario: Badge initialisé à l'ouverture de l'interface React

- **WHEN** le praticien ouvre l'application React/Tauri
- **THEN** le frontend interroge le backend au chargement et le badge de la cloche
  reflète le nombre de rappels `du` + `a_envoyer` non lus

#### Scenario: Rafraîchissement si l'app est déjà ouverte à l'échéance

- **WHEN** la tâche planifiée s'exécute et traite des rappels alors que l'interface
  React est déjà ouverte
- **THEN** l'interface présente les nouveaux rappels dus sans nécessiter de rechargement
  complet (rafraîchissement périodique ou à l'activation de la fenêtre)

### Requirement: Gestion du cycle de vie d'un rappel

Le système SHALL permettre de lister les rappels filtrés par état (à venir, dus, lus,
traités, annulés), de les modifier tant qu'ils ne sont pas envoyés/traités, et de les
annuler. L'annulation SHALL empêcher toute mise en file ou notification ultérieure. Un
rappel `message_patient` ignoré depuis la cloche passe à `lu` : il sort du badge et du
panneau cloche mais reste accessible et envoyable depuis la liste complète et l'onglet
fiche patient.

#### Scenario: Annuler un rappel planifié

- **WHEN** le praticien annule un rappel à l'état `planifie`
- **THEN** le système fait passer le rappel à l'état `annule` et la tâche planifiée ne le
  met jamais en file ni ne le notifie

#### Scenario: Marquer une alerte interne comme traitée

- **WHEN** le praticien marque une alerte interne due comme traitée
- **THEN** le système fait passer le rappel à l'état `traite` et ne le présente plus parmi
  les rappels actifs

#### Scenario: Envoyer un rappel lu depuis la liste complète

- **WHEN** le praticien ouvre la liste complète et envoie via WhatsApp un rappel à
  l'état `lu`
- **THEN** le système ouvre le lien `wa.me` et, après confirmation, fait passer le rappel
  à l'état `envoye`

### Requirement: Configuration des rappels dans le Paramétrage

Le système SHALL exposer dans l'écran Paramétrage une section « Rappels » permettant de
configurer les éléments suivants, stockés dans la table `meta` :
- L'activation des **notifications Windows 11 natives** (activé par défaut)
- L'intervalle de vérification de la tâche planifiée (défaut : 15 min)
- L'indicatif pays par défaut pour la normalisation des numéros (défaut : `+216`)
- L'état de la tâche planifiée (présente / active / inactive), affiché en lecture seule

#### Scenario: Désactiver les notifications Windows

- **WHEN** le praticien désactive les notifications Windows dans le Paramétrage
- **THEN** la tâche planifiée continue de mettre les rappels en file mais n'émet plus
  aucune notification native Windows 11

#### Scenario: État de la tâche planifiée visible

- **WHEN** le praticien ouvre la section Rappels du Paramétrage
- **THEN** le système affiche si la tâche planifiée Windows est présente et active, avec
  un indicateur visuel (présente/active, présente/inactive, absente)

### Requirement: Exposition via l'API backend (FastAPI)

Le système SHALL exposer les opérations sur les rappels via des routes FastAPI
(routeur dédié `crm/routers/rappels.py`, enregistré dans `crm/server.py`) protégées
par le jeton de session, sur le même modèle que les autres routeurs (`patients`,
`documents`, etc.). Les routes SHALL couvrir : création, lecture filtrée par état,
lecture filtrée par patient, mise à jour, annulation, transitions d'état (marquer
lu / envoyé / traité), récupération des rappels dus, et comptage pour le badge cloche.

#### Scenario: Création d'un rappel via l'API

- **WHEN** le frontend POST `/api/rappels` avec un payload valide
- **THEN** le backend valide, persiste le rappel et retourne le rappel créé avec son
  `id` et son état `planifie`

#### Scenario: Refus d'un rappel invalide via l'API

- **WHEN** le frontend POST `/api/rappels` avec un `message_patient` sans patient ou
  sans numéro `is_whatsapp = 1` exploitable
- **THEN** le backend retourne une erreur structurée (code stable, message FR) sans
  créer d'entrée en base

#### Scenario: Comptage pour le badge cloche

- **WHEN** le frontend GET `/api/rappels/count-actifs`
- **THEN** le backend retourne le nombre de rappels à état `du` + rappels `a_envoyer`
  avec `lu = 0`, utilisé pour afficher le badge numérique sur l'icône cloche
