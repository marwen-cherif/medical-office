## ADDED Requirements

### Requirement: Catalogue d'actes tarifés
Le système SHALL fournir un référentiel d'actes, chaque acte portant au minimum un
**libellé** et un **prix**. Un acte SHALL aussi porter un indicateur **actif** (présent
ou retiré des listes de saisie) et un **ordre d'affichage**. Le prix SHALL être un nombre
formaté à l'affichage selon la convention française (espace pour les milliers, virgule
décimale).

#### Scenario: Un acte porte un libellé et un prix
- **WHEN** l'utilisateur consulte le référentiel
- **THEN** chaque acte affiche son libellé et son prix formaté

#### Scenario: Prix affiché au format français
- **WHEN** un acte a un prix de 1800
- **THEN** le prix est affiché « 1 800,00 »

### Requirement: Création d'un acte
Le système SHALL permettre de créer un acte en renseignant son libellé et son prix.
Le libellé SHALL être obligatoire et non vide ; le prix SHALL être un nombre positif ou
nul. Un acte créé SHALL être **actif** par défaut.

#### Scenario: Création d'un acte valide
- **WHEN** l'utilisateur crée un acte « Détartrage » au prix 120
- **THEN** l'acte « Détartrage » apparaît dans le référentiel, actif, au prix 120

#### Scenario: Refus d'un libellé vide
- **WHEN** l'utilisateur tente de créer un acte sans libellé
- **THEN** la création est refusée avec un message d'erreur et aucun acte n'est créé

#### Scenario: Avertissement de libellé déjà existant
- **WHEN** l'utilisateur crée un acte dont le libellé correspond à un acte actif existant
- **THEN** un avertissement non bloquant est présenté, l'utilisateur pouvant confirmer ou
  corriger

### Requirement: Édition d'un acte
Le système SHALL permettre de modifier le libellé et le prix d'un acte existant. La
modification du prix SHALL n'affecter que les usages **futurs** : les valeurs déjà
recopiées ailleurs (snapshots) ne SHALL PAS être modifiées rétroactivement par ce change.

#### Scenario: Modification du prix d'un acte
- **WHEN** l'utilisateur change le prix de « Composite » de 180 à 200
- **THEN** le référentiel affiche « Composite » au prix 200

### Requirement: Retrait non destructif d'un acte
Le système SHALL permettre de retirer un acte du catalogue en le marquant **inactif**
plutôt qu'en le supprimant. Un acte inactif SHALL être exclu des listes de saisie par
défaut, mais SHALL rester en base et SHALL pouvoir être réactivé. La suppression
définitive ne SHALL être proposée que pour un acte qui n'a jamais été utilisé.

#### Scenario: Désactivation d'un acte
- **WHEN** l'utilisateur retire l'acte « Couronne céramique »
- **THEN** l'acte n'apparaît plus dans les listes de saisie mais reste consultable parmi
  les actes inactifs

#### Scenario: Réactivation d'un acte
- **WHEN** l'utilisateur réactive un acte inactif
- **THEN** l'acte réapparaît dans les listes de saisie

### Requirement: Recherche et pagination des actes
Le système SHALL permettre de rechercher un acte par son libellé, de façon insensible aux
accents et à la casse, et SHALL paginer la liste des actes (taille de page cohérente avec
le reste de l'application). La liste SHALL pouvoir, en option, inclure les actes inactifs.

#### Scenario: Recherche par libellé
- **WHEN** l'utilisateur saisit « couron » dans la recherche
- **THEN** seuls les actes dont le libellé correspond (ex. « Couronne céramique ») sont
  listés

#### Scenario: Pagination de la liste
- **WHEN** le référentiel contient plus d'actes que la taille d'une page
- **THEN** la liste est paginée avec un indicateur de plage et des contrôles
  précédent / suivant

### Requirement: Onglet de paramétrage dédié aux actes
L'écran de Paramétrage SHALL exposer un onglet « Actes » regroupant la recherche, la liste
paginée et les actions de création, d'édition et de retrait, suivant le même patron
d'interface que les onglets de modèles existants.

#### Scenario: Accès à la gestion des actes
- **WHEN** l'utilisateur ouvre Paramétrage › Actes
- **THEN** il voit la liste paginée des actes avec un champ de recherche et une action de
  création

### Requirement: Exposition du prix pour pré-remplissage
Le référentiel SHALL exposer une lecture permettant à d'autres fonctionnalités d'obtenir,
pour un acte, son libellé et son prix courant, afin de **pré-remplir** un montant. Le
référentiel ne SHALL PAS, dans ce périmètre, réaliser lui-même ce pré-remplissage : il en
fournit seulement la donnée.

#### Scenario: Lecture d'un acte pour pré-remplissage
- **WHEN** une fonctionnalité consommatrice demande l'acte « Implant »
- **THEN** le référentiel renvoie son libellé et son prix courant

### Requirement: Préservation des données et migration additive
L'introduction du référentiel SHALL être **purement additive** : une nouvelle table créée
via `CREATE TABLE IF NOT EXISTS`, un bump de `SCHEMA_VERSION`, et un snapshot
pré-migration. Aucune donnée existante (patients, documents, paiements, fichiers générés)
ne SHALL être modifiée ou supprimée par la mise à niveau.

#### Scenario: Mise à niveau d'une base de production
- **WHEN** une base de production existante est ouverte par la nouvelle version
- **THEN** la table des actes est créée vide, les données existantes restent intactes, et
  un snapshot pré-migration est conservé
