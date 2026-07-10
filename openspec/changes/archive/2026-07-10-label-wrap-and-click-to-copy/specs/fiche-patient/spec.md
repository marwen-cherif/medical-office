# fiche-patient

## MODIFIED Requirements

### Requirement: Colonne d'identité compacte

La colonne d'identité SHALL afficher de façon compacte : le bouton de retour à la liste,
le nom affiché du patient, ses coordonnées (email, téléphone), sa date de naissance, son
adresse, et un résumé des montants clés (au moins « Dû » et « Reste à recouvrer »). Elle
SHALL contenir le bouton « Modifier » donnant accès à l'édition de la fiche. Les coordonnées
du patient (email, téléphone, date de naissance, adresse) SHALL être présentées de façon à
ne pas déborder ni avoir de retour à la ligne indésirable, et SHALL intégrer le mécanisme
de copie rapide `ClickToCopy` pour pouvoir être copiées d'un simple clic.

#### Scenario: Coordonnées et montants visibles d'emblée

- **WHEN** la fiche d'un patient est affichée
- **THEN** la colonne d'identité montre nom, email, téléphone, date de naissance, adresse
- **AND** affiche le montant Dû et le Reste à recouvrer du patient

#### Scenario: Copie d'une coordonnée

- **WHEN** l'utilisateur clique sur l'email, le téléphone, l'adresse ou la date de naissance dans la colonne d'identité
- **THEN** la valeur associée est copiée dans le presse-papiers via le composant ClickToCopy

#### Scenario: Édition depuis l'identité

- **WHEN** l'utilisateur clique sur « Modifier » (ou utilise le raccourci d'édition)
- **THEN** le dialogue d'édition de la fiche patient s'ouvre
