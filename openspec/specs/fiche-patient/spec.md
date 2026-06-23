# fiche-patient

## Purpose

Refondre la page de détail d'un patient en une disposition à **colonne d'identité figée**
(contexte patient toujours visible) et **zone de contenu en onglets** (Plans & actes,
Documents, Règlements, Historique). La refonte est **à parité fonctionnelle** : aucune
action ni raccourci existant n'est retiré, et le comportement est identique en mode desktop
et en mode web (même code `crm/app.py`).

## Requirements

### Requirement: Disposition en colonne d'identité figée et contenu en onglets

La page de détail d'un patient SHALL être organisée en deux zones horizontales : une
**colonne d'identité** de largeur fixe à gauche et une **zone de contenu** extensible à
droite. La colonne d'identité SHALL rester visible (figée) lorsque l'utilisateur navigue
entre les onglets de la zone de contenu, de sorte que le contexte patient soit toujours
affiché.

#### Scenario: Affichage initial de la fiche

- **WHEN** l'utilisateur ouvre la fiche d'un patient
- **THEN** la colonne d'identité est affichée à gauche et la zone de contenu à droite
- **AND** l'onglet « Plans & actes » est sélectionné par défaut

#### Scenario: L'identité reste visible en changeant d'onglet

- **WHEN** l'utilisateur sélectionne un autre onglet (Documents, Règlements ou Historique)
- **THEN** seule la zone de contenu de droite change
- **AND** la colonne d'identité à gauche reste affichée à l'identique

### Requirement: Colonne d'identité compacte

La colonne d'identité SHALL afficher de façon compacte : le bouton de retour à la liste,
le nom affiché du patient, ses coordonnées (email, téléphone), sa date de naissance, son
adresse, et un résumé des montants clés (au moins « Dû » et « Reste à recouvrer »). Elle
SHALL contenir le bouton « Modifier » donnant accès à l'édition de la fiche. L'email et le
téléphone SHALL rester cliquables pour copie, comme dans la fiche actuelle.

#### Scenario: Coordonnées et montants visibles d'emblée

- **WHEN** la fiche d'un patient est affichée
- **THEN** la colonne d'identité montre nom, email, téléphone, date de naissance, adresse
- **AND** affiche le montant Dû et le Reste à recouvrer du patient

#### Scenario: Copie d'une coordonnée

- **WHEN** l'utilisateur clique sur l'email ou le téléphone dans la colonne d'identité
- **THEN** la valeur est copiée dans le presse-papiers

#### Scenario: Édition depuis l'identité

- **WHEN** l'utilisateur clique sur « Modifier » (ou utilise le raccourci d'édition)
- **THEN** le dialogue d'édition de la fiche patient s'ouvre

### Requirement: Navigation par onglets de la zone de contenu

La zone de contenu SHALL présenter au moins quatre onglets : « Plans & actes »,
« Documents », « Règlements » et « Historique ». À tout instant, un seul onglet SHALL être
affiché. La sélection d'un onglet SHALL afficher le contenu correspondant sans recharger
la colonne d'identité.

#### Scenario: Sélection d'un onglet

- **WHEN** l'utilisateur clique sur l'onglet « Documents »
- **THEN** la zone de contenu affiche la liste des documents du patient
- **AND** les autres contenus d'onglet ne sont pas affichés

### Requirement: Conservation des fonctionnalités Plans & actes

L'onglet « Plans & actes » SHALL conserver l'ensemble des fonctionnalités actuelles :
résumé des actes en attente de règlement, actes isolés, plans de traitement dépliables
avec leurs prestations, barres de progression de paiement, badges de dents, et les actions
« Plan », « Acte », « Régler », ainsi que l'ajout/édition/suppression de plan et d'acte.

#### Scenario: Ajout d'un plan depuis l'onglet

- **WHEN** l'utilisateur clique sur « Plan » dans l'onglet « Plans & actes »
- **THEN** le dialogue de création de plan de traitement s'ouvre
- **AND** après création le plan apparaît dans la liste de l'onglet

#### Scenario: Règlement d'un acte conservé

- **WHEN** un acte facturable a un reste à régler dans l'onglet « Plans & actes »
- **THEN** l'action « Régler cet acte » reste disponible sur la ligne de l'acte

### Requirement: Conservation des fonctionnalités Documents

L'onglet « Documents » SHALL conserver le regroupement des documents par catégorie
(pastille couleur/icône + compteur), la pagination existante, et toutes les actions par
document (générer depuis un brouillon, ouvrir le fichier, imprimer, envoyer par email,
rafraîchir le statut Mailjet). Les actions « Note d'honoraires », « Générer un document »
et « Rafraîchir les statuts » SHALL rester accessibles dans cet onglet.

#### Scenario: Regroupement par catégorie préservé

- **WHEN** le patient possède des documents de plusieurs catégories
- **THEN** l'onglet « Documents » regroupe les documents par catégorie avec compteur
- **AND** l'ordre connu → inconnu → « Sans catégorie » est respecté

#### Scenario: Génération d'un document depuis l'onglet

- **WHEN** l'utilisateur clique sur « Générer un document » (ou utilise le raccourci)
- **THEN** le flux de génération de document démarre comme actuellement

### Requirement: Conservation des fonctionnalités Règlements

L'onglet « Règlements » SHALL conserver le résumé des montants (Dû / Encaissé / Reste à
recouvrer) et l'historique des règlements encaissés, avec la pagination existante.

#### Scenario: Résumé et historique des règlements

- **WHEN** l'utilisateur sélectionne l'onglet « Règlements »
- **THEN** la zone de contenu affiche le résumé Dû / Encaissé / Reste à recouvrer
- **AND** affiche la liste des règlements encaissés (paginée si nécessaire)

### Requirement: Parité fonctionnelle desktop et web

La nouvelle disposition SHALL fonctionner de manière identique en mode desktop et en mode
web (même code `crm/app.py`). Aucune action ni raccourci existant de la fiche patient ne
SHALL être retiré par la refonte.

#### Scenario: Aucune perte d'action

- **WHEN** on compare la fiche refondue à la fiche actuelle
- **THEN** chaque action existante (générer, imprimer, envoyer, régler, ajouter/éditer/
  supprimer plan et acte, modifier la fiche) reste accessible dans l'un des onglets ou la
  colonne d'identité
