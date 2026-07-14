## MODIFIED Requirements

### Requirement: Colonne d'identité compacte

La colonne d'identité SHALL afficher de façon compacte : le bouton de retour à la liste, le nom affiché du patient, ses coordonnées (email, liste des téléphones avec relation et badge WhatsApp), sa date de naissance, son adresse, et un résumé des montants clés (au moins « Dû » et « Reste à recouvrer »). Elle SHALL contenir le bouton « Modifier » donnant accès à l'édition de la fiche. Les coordonnées du patient SHALL être présentées de façon à ne pas déborder ni avoir de retour à la ligne indésirable, et SHALL intégrer le mécanisme de copie rapide `ClickToCopy` pour pouvoir être copiées d'un simple clic.

#### Scenario: Coordonnées et montants visibles d'emblée
- **WHEN** la fiche d'un patient est affichée
- **THEN** la colonne d'identité montre nom, email, la liste des numéros de téléphone avec leur relation et indicateur WhatsApp, la date de naissance et l'adresse
- **AND** affiche le montant Dû et le Reste à recouvrer du patient

#### Scenario: Copie d'une coordonnée
- **WHEN** l'utilisateur clique sur l'email, un des téléphones, l'adresse ou la date de naissance dans la colonne d'identité
- **THEN** la valeur associée est copiée dans le presse-papiers via le composant ClickToCopy

#### Scenario: Édition depuis l'identité
- **WHEN** l'utilisateur clique sur « Modifier » (ou utilise le raccourci d'édition)
- **THEN** le dialogue d'édition de la fiche patient s'ouvre

## ADDED Requirements

### Requirement: Gestion de plusieurs numéros de téléphone
Le système SHALL permettre de gérer plusieurs numéros de téléphone pour un patient. Lors de la création ou de la modification d'un patient via le dialogue d'édition, l'utilisateur SHALL pouvoir ajouter ou supprimer des lignes de numéros de téléphone. Pour chaque ligne de téléphone, le système SHALL permettre de saisir le numéro, de spécifier la relation avec le patient (Lui-même, Le conjoint, Père, Mère, L'enfant, ou un texte libre) et d'activer/désactiver le support de WhatsApp pour ce numéro.

#### Scenario: Ajout d'une ligne téléphonique
- **WHEN** l'utilisateur clique sur le bouton pour ajouter un numéro de téléphone dans le dialogue d'édition du patient
- **THEN** une nouvelle ligne de saisie apparaît avec un champ de sélection de relation vide, un champ de numéro de téléphone vide, et le bouton WhatsApp désactivé par défaut

#### Scenario: Enregistrement des téléphones du patient
- **WHEN** l'utilisateur saisit plusieurs numéros de téléphone avec différentes relations et états WhatsApp puis enregistre
- **THEN** le système associe ces numéros au patient et ferme le dialogue

### Requirement: Saisie de téléphone avec indicateur de pays et indicatif
Le champ de numéro de téléphone dans le dialogue d'édition SHALL intégrer un sélecteur de pays affichant le drapeau et l'indicatif téléphonique international (ex. Tunisie +216, France +33). Par défaut, l'indicatif affiché correspond à celui des paramètres généraux. L'utilisateur SHALL pouvoir modifier le pays sélectionné, ce qui met à jour l'indicatif associé.

#### Scenario: Changement de pays dans le sélecteur
- **WHEN** l'utilisateur sélectionne un pays différent dans le menu déroulant du champ téléphone
- **THEN** le drapeau et l'indicatif téléphonique international de la ligne sont mis à jour en conséquence
