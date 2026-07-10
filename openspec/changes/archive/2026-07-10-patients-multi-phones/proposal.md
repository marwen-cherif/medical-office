## Why

Permettre la gestion de plusieurs numéros de téléphone par patient (notamment pour associer les contacts des proches comme le conjoint, le père, la mère, etc.) et spécifier pour chaque ligne si elle supporte WhatsApp. Cela résout la limitation actuelle d'un seul numéro par patient, améliore l'ergonomie de saisie via un sélecteur de pays avec indicatif, et permet de choisir sur quelle ligne envoyer un document par WhatsApp en cas de lignes multiples configurées.

## What Changes

- **Base de données SQLite** : Ajout d'une table `patient_phones` pour enregistrer plusieurs numéros par patient, avec pour chacun un champ relation (Lui-même, Conjoint, Père, Mère, Enfant, Autre), un drapeau indiquant si la ligne supporte WhatsApp, et son indicatif de pays.
- **Migration** : v15 de schéma effectuant un backfill automatique des numéros existants de `patients.telephone` vers la nouvelle table avec la relation par défaut "Lui-même".
- **Backend FastAPI** :
  - Mise à jour des schémas Pydantic de création/modification de patient pour accepter la liste des numéros de téléphone.
  - Mise à jour des routes CRUD des patients pour lire et écrire dans la table `patient_phones`.
  - Modification de l'endpoint `POST /documents/{document_id}/send-whatsapp` pour recevoir optionnellement le numéro destinataire cible dans le corps de la requête.
- **Frontend React** :
  - Intégration d'un champ de saisie téléphonique avec sélecteur de pays (drapeau et indicatif) et validation.
  - Formulaire patient (`PatientFormDialog`) enrichi pour permettre d'ajouter/supprimer dynamiquement des numéros de téléphone (lignes de proches) avec choix de la relation (suggestions et texte libre) et commutateur WhatsApp.
  - Fiche patient (`PatientDetail` dans la colonne d'identité figée) mise à jour pour lister tous les numéros avec copie rapide (`ClickToCopy`) et badges (WhatsApp, relation).
  - Écran des documents et liste des travaux : lors du clic sur le bouton « Envoyer par WhatsApp », si plusieurs numéros compatibles WhatsApp sont configurés pour le patient, ouverture d'une boîte de dialogue permettant de sélectionner la ligne destinataire.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `fiche-patient` : Prise en charge et affichage de plusieurs numéros de téléphone associés à des relations et tags WhatsApp dans la fiche patient et son formulaire.
- `envoi-whatsapp` : Possibilité de choisir le numéro destinataire lors de l'envoi WhatsApp d'un document si le patient possède plusieurs numéros compatibles.

## Impact

- **Database** : Nouvelle table `patient_phones` reliée à `patients(id)` par clé étrangère.
- **API** : Modification des schémas JSON et types TypeScript générés pour les patients. Modification de l'API d'envoi WhatsApp.
- **Frontend** : Composant de formulaire patient et écrans d'envoi de documents (choix de la ligne).
