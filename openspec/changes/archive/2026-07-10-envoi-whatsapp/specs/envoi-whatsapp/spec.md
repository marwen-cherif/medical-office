## ADDED Requirements

### Requirement: Configuration des identifiants WhatsApp

Le système SHALL permettre de saisir et mémoriser les identifiants de l'API
Meta WhatsApp Cloud dans un onglet dédié de Paramétrage › WhatsApp : Phone
Number ID, token d'accès, langue du modèle, et la correspondance « type de
document → nom de modèle Meta approuvé ». L'indicatif pays par défaut utilisé
pour la normalisation des numéros n'est PAS redéfini ici : le système SHALL
réutiliser le réglage partagé d'indicatif par défaut déjà fourni par la
fonctionnalité de rappels. Le token d'accès SHALL être traité comme un secret
(jamais affiché en clair une fois enregistré, jamais journalisé).

#### Scenario: Enregistrement des identifiants

- **WHEN** l'utilisateur saisit le Phone Number ID, le token, la langue et au
  moins une correspondance type → modèle dans Paramétrage › WhatsApp et valide
- **THEN** le système enregistre ces réglages et confirme l'enregistrement

#### Scenario: Identifiants incomplets

- **WHEN** l'utilisateur tente d'envoyer un document par WhatsApp alors qu'un
  identifiant obligatoire (Phone Number ID ou token) n'est pas configuré
- **THEN** le système refuse l'envoi et redirige l'utilisateur vers
  Paramétrage › WhatsApp avec un message explicite

#### Scenario: Token masqué après enregistrement

- **WHEN** l'utilisateur rouvre Paramétrage › WhatsApp après avoir enregistré un token
- **THEN** le système n'affiche pas le token en clair (champ masqué ou indication
  qu'un token est déjà configuré sans le révéler)

### Requirement: Bouton d'envoi WhatsApp

Le système SHALL afficher un bouton « Envoyer par WhatsApp » sur chaque ligne
de document, dans la vue fiche patient et dans la page Documents, lorsque le
patient possède un numéro de téléphone renseigné et que le document est généré
(fichier présent). Le bouton SHALL coexister avec le bouton d'envoi par email
sans le remplacer.

#### Scenario: Bouton visible pour un patient avec téléphone

- **WHEN** un document est généré et que le patient a un numéro de téléphone
- **THEN** le système affiche le bouton « Envoyer par WhatsApp » sur la ligne du document

#### Scenario: Bouton masqué sans téléphone

- **WHEN** un document est généré mais que le patient n'a aucun numéro de téléphone
- **THEN** le système n'affiche pas le bouton WhatsApp

#### Scenario: Coexistence avec l'email

- **WHEN** un patient a à la fois un email et un téléphone et que le document est généré
- **THEN** le système affiche les deux boutons d'envoi (email et WhatsApp) indépendamment

### Requirement: Envoi d'un document par WhatsApp

Le système SHALL envoyer le fichier déjà généré (PDF ou JPG dans `output/`) au
numéro WhatsApp du patient via l'API Meta WhatsApp Cloud : upload du fichier
sur l'endpoint média de Meta pour obtenir un identifiant média, puis envoi d'un
message utilisant le modèle approuvé avec le document en pièce jointe. L'envoi
SHALL s'exécuter côté serveur (machine où tourne l'application), de façon
identique en mode desktop et en mode web. L'envoi SHALL être lancé en tâche de
fond avec indicateur de chargement, sans figer l'interface.

#### Scenario: Envoi réussi

- **WHEN** l'utilisateur confirme l'envoi WhatsApp d'un document généré pour un
  patient ayant un téléphone valide et des identifiants configurés
- **THEN** le système uploade le fichier, envoie le message avec pièce jointe,
  enregistre l'identifiant de message retourné et passe le statut WhatsApp du
  document à « envoyé »

#### Scenario: Fichier introuvable

- **WHEN** l'utilisateur déclenche un envoi WhatsApp mais que le fichier du
  document n'existe plus sur le disque
- **THEN** le système refuse l'envoi et signale que le fichier est introuvable,
  sans modifier le statut

#### Scenario: Échec de l'API

- **WHEN** l'API Meta retourne une erreur (token invalide, numéro non joignable,
  modèle non approuvé, quota dépassé…)
- **THEN** le système passe le statut WhatsApp du document à « erreur » et
  conserve le message d'erreur pour diagnostic, sans interrompre l'application

### Requirement: Choix du modèle par type de document et variables du message

Le système SHALL sélectionner le modèle Meta à utiliser d'après le type du
document envoyé, selon la correspondance « type → modèle » configurée. Plusieurs
types SHALL pouvoir pointer vers le même modèle. Le message SHALL injecter dans
le modèle les variables prénom, nom et type de document — et uniquement
celles-ci (aucun montant dans le corps du message). Si aucun modèle n'est
associé au type du document, le système SHALL refuser l'envoi et renvoyer vers
Paramétrage › WhatsApp.

#### Scenario: Modèle résolu par type

- **WHEN** un document d'un type donné est envoyé et qu'un modèle est associé à ce type
- **THEN** le système envoie le message via ce modèle, en injectant prénom, nom
  et type de document

#### Scenario: Modèle partagé entre plusieurs types

- **WHEN** plusieurs types de documents sont configurés vers le même modèle Meta
- **THEN** le système utilise ce modèle commun pour chacun de ces types

#### Scenario: Type sans modèle associé

- **WHEN** l'utilisateur tente d'envoyer par WhatsApp un document dont le type
  n'a aucun modèle associé
- **THEN** le système refuse l'envoi et invite à configurer le modèle dans
  Paramétrage › WhatsApp

### Requirement: Normalisation du numéro de téléphone

Le système SHALL normaliser le numéro de téléphone du patient au format
international E.164 avant l'envoi, en appliquant l'indicatif pays par défaut
configuré (réglage partagé, +216 par défaut, paramétrable) lorsque le numéro est
saisi en format local. Si le numéro ne peut pas
être normalisé en un format plausible, le système SHALL refuser l'envoi avec un
message clair plutôt que d'appeler l'API avec un numéro invalide.

#### Scenario: Numéro local normalisé

- **WHEN** le patient a un numéro saisi en format local et qu'un préfixe pays
  par défaut est configuré
- **THEN** le système convertit le numéro au format E.164 avant l'appel à l'API

#### Scenario: Numéro inexploitable

- **WHEN** le numéro de téléphone du patient ne peut pas être converti en un
  format E.164 plausible
- **THEN** le système refuse l'envoi et invite à corriger le numéro du patient

### Requirement: Suivi du statut de remise WhatsApp

Le système SHALL stocker, par document, un statut d'envoi WhatsApp distinct du
statut email (envoyé / remis / lu / erreur) et SHALL permettre de rafraîchir ce
statut auprès de l'API Meta, à l'image du rafraîchissement du statut Mailjet.
Les statuts email et WhatsApp d'un même document SHALL être indépendants l'un de
l'autre.

#### Scenario: Affichage du statut WhatsApp

- **WHEN** un document a été envoyé par WhatsApp
- **THEN** le système affiche un libellé de statut WhatsApp dédié sur la ligne du document

#### Scenario: Rafraîchissement du statut

- **WHEN** l'utilisateur demande le rafraîchissement du statut WhatsApp d'un
  document envoyé
- **THEN** le système interroge l'API Meta et met à jour le statut (remis, lu…)
  ainsi que l'horodatage du dernier rafraîchissement

#### Scenario: Indépendance des canaux

- **WHEN** un document a été envoyé par email mais pas par WhatsApp (ou l'inverse)
- **THEN** le système conserve et affiche les deux statuts séparément sans que
  l'un n'écrase l'autre

### Requirement: Préservation des données existantes

Le système SHALL introduire le suivi WhatsApp par une migration additive
(expand-only) : nouvelles colonnes nullable sur la table `documents`, sans
suppression ni renommage de colonne existante, avec snapshot de la base avant
migration. Les documents déjà générés et leurs statuts email existants SHALL
rester reconnus et inchangés après la mise à jour.

#### Scenario: Migration d'une base existante

- **WHEN** l'application démarre sur une base de production existante ne
  contenant pas encore les colonnes WhatsApp
- **THEN** le système ajoute les colonnes WhatsApp nullable, conserve tous les
  documents et statuts email existants, et écrit un snapshot pré-migration

#### Scenario: Document antérieur sans statut WhatsApp

- **WHEN** un document généré avant la fonctionnalité est affiché
- **THEN** le système le traite comme « non envoyé par WhatsApp » sans erreur
