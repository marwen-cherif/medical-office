## MODIFIED Requirements

### Requirement: Bouton d'envoi WhatsApp

Le système SHALL afficher un bouton « Envoyer par WhatsApp » sur chaque ligne de document, dans la vue fiche patient et dans la page Documents, lorsque le patient possède au moins un numéro de téléphone renseigné et que le document est généré (fichier présent). Le bouton SHALL coexister avec le bouton d'envoi par email sans le remplacer.

#### Scenario: Bouton visible pour un patient avec téléphone
- **WHEN** un document est généré et que le patient a au moins un numéro de téléphone renseigné
- **THEN** le système affiche le bouton « Envoyer par WhatsApp » sur la ligne du document

#### Scenario: Bouton masqué sans téléphone
- **WHEN** un document est généré mais que le patient n'a aucun numéro de téléphone renseigné
- **THEN** le système n'affiche pas le bouton WhatsApp

#### Scenario: Coexistence avec l'email
- **WHEN** un patient a à la fois un email et un téléphone et que le document est généré
- **THEN** le système affiche les deux boutons d'envoi (email et WhatsApp) indépendamment

### Requirement: Envoi d'un document par WhatsApp

Le système SHALL envoyer le fichier déjà généré (PDF ou JPG dans `output/`) au numéro WhatsApp sélectionné du patient via l'API Meta WhatsApp Cloud : upload du fichier sur l'endpoint média de Meta pour obtenir un identifiant média, puis envoi d'un message utilisant le modèle approuvé avec le document en pièce jointe. L'envoi s'exécute côté serveur (machine où tourne l'application), de façon identique en mode desktop et en mode web. L'envoi SHALL être lancé en tâche de fond avec indicateur de chargement, sans figer l'interface.

#### Scenario: Envoi réussi avec sélection
- **WHEN** l'utilisateur confirme l'envoi WhatsApp d'un document généré après avoir sélectionné l'un des numéros de téléphone valides du patient et que les identifiants de l'API sont configurés
- **THEN** le système uploade le fichier, envoie le message avec pièce jointe à ce numéro spécifique, enregistre l'identifiant de message retourné et passe le statut WhatsApp du document à « envoyé »

#### Scenario: Fichier introuvable
- **WHEN** l'utilisateur déclenche un envoi WhatsApp mais que le fichier du document n'existe plus sur le disque
- **THEN** le système refuse l'envoi et signale que le fichier est introuvable, sans modifier le statut

#### Scenario: Échec de l'API
- **WHEN** l'API Meta retourne une erreur (token invalide, numéro non joignable, modèle non approuvé, quota dépassé…)
- **THEN** le système passe le statut WhatsApp du document à « erreur » et conserve le message d'erreur pour diagnostic, sans interrompre l'application

## ADDED Requirements

### Requirement: Sélection de la ligne WhatsApp destinataire

Lorsque l'utilisateur clique sur le bouton « Envoyer par WhatsApp », si le patient possède plusieurs numéros de téléphone enregistrés, le système SHALL :
- Envoyer directement au numéro si c'est le seul disponible ou le seul avec le commutateur WhatsApp activé.
- Afficher un dialogue de sélection si plusieurs numéros ont le commutateur WhatsApp activé ou si aucun ne l'a mais qu'il y a plusieurs numéros. Le dialogue doit afficher la liste des numéros, la relation associée, et un indicateur visuel pour les numéros compatibles WhatsApp. L'utilisateur peut ainsi sélectionner la ligne cible avant de confirmer l'envoi.

#### Scenario: Choix du destinataire parmi plusieurs numéros WhatsApp
- **WHEN** l'utilisateur clique sur le bouton « Envoyer par WhatsApp » pour un patient ayant plusieurs numéros de téléphone configurés avec WhatsApp actif
- **THEN** le système affiche une boîte de dialogue listant ces numéros avec leur relation et un indicateur WhatsApp
- **AND** après sélection et validation de l'utilisateur, l'envoi est initié vers ce numéro précis

#### Scenario: Avertissement si aucun numéro n'a WhatsApp actif
- **WHEN** l'utilisateur clique sur le bouton « Envoyer par WhatsApp » pour un patient ayant plusieurs numéros de téléphone mais aucun n'a WhatsApp actif
- **THEN** le système affiche la boîte de dialogue de sélection avec tous les numéros mais affiche un avertissement indiquant qu'aucun numéro n'a été expressément déclaré compatible avec WhatsApp
