## ADDED Requirements

### Requirement: Type de template « tableau »

Le système SHALL permettre qu'un template de document soit de type « tableau » :
en plus des balises document mono-valeur (`<TAG>`), il déclare un **bloc de lignes
répétables** constitué de **colonnes typées** (par exemple `date`, `acte`,
`quantite`, `prix_unitaire`, `montant`). Un template SHALL être soit « simple »
(comportement actuel inchangé), soit « tableau » ; les deux types coexistent.

#### Scenario: Détection d'un template tableau

- **WHEN** un template contient au moins une **balise de ligne** (préfixe convenu,
  ex. `<L_DATE>`) dans une cellule de tableau Word
- **THEN** le système le considère comme un template « tableau » et expose ses
  colonnes de ligne, distinctes des balises document

#### Scenario: Template simple inchangé

- **WHEN** un template ne contient aucune balise de ligne
- **THEN** il est traité comme un template « simple » et son rendu est identique à
  celui d'avant ce changement (une valeur par balise, aucun bloc répétable)

### Requirement: Déclaration des colonnes de ligne et des champs calculés

Le système SHALL permettre de configurer, par template « tableau », la liste des
**colonnes de ligne** (nom de colonne, libellé, type `text | number | date`) et la
liste des **champs calculés** (colonnes calculées par ligne et agrégats document).
Cette configuration SHALL être additive et n'altère aucune donnée existante.

#### Scenario: Colonnes de ligne configurées

- **WHEN** l'utilisateur définit les colonnes `date`, `acte`, `quantite`,
  `prix_unitaire` pour un template tableau
- **THEN** la saisie d'une ligne propose exactement ces colonnes avec leur type, et
  une colonne calculée déclarée (ex. `montant`) n'est pas saisie à la main

#### Scenario: Type de colonne respecté

- **WHEN** une colonne est typée `date`
- **THEN** elle est saisie via le sélecteur de date et rendue au format `jj/mm/aaaa`,
  cohérent avec le formatage des balises `DATE` existantes

### Requirement: Saisie ligne à ligne dans la fiche patient

Le système SHALL permettre, lors de la création/édition d'un document fondé sur un
template tableau, d'**ajouter, supprimer et réordonner** des lignes une à une. Le
**total** SHALL être recalculé et affiché en direct à chaque modification.

#### Scenario: Ajout et suppression de lignes

- **WHEN** l'utilisateur ajoute une 1re ligne (01/05/2026, Détartrage, 80,000) puis
  une 2e ligne, puis supprime la 1re
- **THEN** le document ne conserve que la 2e ligne et le total affiché reflète cette
  seule ligne

#### Scenario: Réordonnancement

- **WHEN** l'utilisateur déplace une ligne vers le haut
- **THEN** l'ordre de saisie est conservé et le document généré rend les lignes dans
  ce nouvel ordre

#### Scenario: Total en direct

- **WHEN** l'utilisateur modifie le montant d'une ligne
- **THEN** le total affiché est recalculé immédiatement, sans génération du document

### Requirement: Répétition dynamique de la ligne-modèle Word

Le moteur de remplissage SHALL **dupliquer** la ligne-modèle d'un tableau Word
(la ligne contenant les balises de ligne) **autant de fois qu'il y a de lignes
saisies**, en remplaçant dans chaque copie les balises de ligne par les valeurs de
la ligne correspondante, **en préservant la mise en forme** de la ligne-modèle. Cette
fonctionnalité SHALL être **additive** et ne modifie pas la logique existante de
redistribution de texte entre runs (`_replace_in_para_elem`).

#### Scenario: Une ligne-modèle dupliquée par acte

- **WHEN** un document tableau a 4 lignes saisies et un template avec une seule
  ligne-modèle `<L_DATE> | <L_ACTE> | <L_MONTANT>`
- **THEN** le tableau rendu contient 4 lignes de données, chacune portant les valeurs
  de sa ligne, et la ligne-modèle d'origine n'apparaît pas vide

#### Scenario: Mise en forme préservée

- **WHEN** la ligne-modèle a une mise en forme (gras, alignement, bordures)
- **THEN** chaque ligne dupliquée conserve cette mise en forme

#### Scenario: Zéro ligne saisie

- **WHEN** aucune ligne n'est saisie pour un document tableau
- **THEN** le tableau ne contient aucune ligne de données (la ligne-modèle n'est pas
  rendue avec des balises non remplacées)

#### Scenario: Balises document hors tableau inchangées

- **WHEN** le template contient aussi des balises document (`<NOM>`, `<TOTAL>`, …) en
  dehors de la ligne-modèle
- **THEN** elles sont remplacées une seule fois, comme aujourd'hui, sans duplication

### Requirement: Valeurs calculées bornées

Le système SHALL calculer des valeurs dérivées via un **évaluateur borné et sûr**
(sans `eval`), supportant : pour les **colonnes calculées par ligne**, l'arithmétique
`+ - * /` et les parenthèses sur les colonnes numériques de la **même** ligne ; pour
les **agrégats document**, les fonctions `SUM`, `COUNT`, `AVG`, `MIN`, `MAX` sur une
colonne de ligne. Les montants calculés SHALL être formatés en style français (espace
pour les milliers, virgule décimale) cohérent avec `format_montant`.

#### Scenario: Colonne calculée par ligne

- **WHEN** une colonne `montant` est définie par `quantite * prix_unitaire` et une
  ligne porte `quantite = 2`, `prix_unitaire = 60`
- **THEN** la colonne `montant` rendue pour cette ligne vaut `120,000`

#### Scenario: Agrégat document

- **WHEN** `<TOTAL>` est défini par `SUM(montant)` sur des lignes de montants
  80, 120, 40, 150
- **THEN** `<TOTAL>` rendu vaut `390,000`

#### Scenario: Agrégat de comptage

- **WHEN** `<NB_ACTES>` est défini par `COUNT(montant)` sur 4 lignes
- **THEN** `<NB_ACTES>` rendu vaut `4`

#### Scenario: Expression invalide rejetée sans exécution de code

- **WHEN** un champ calculé contient une expression non supportée (appel de fonction
  inconnue, opérateur interdit, référence à une colonne inexistante)
- **THEN** la génération signale une erreur explicite et **n'exécute aucun code
  arbitraire** ; aucun document erroné n'est produit silencieusement

#### Scenario: Division par zéro maîtrisée

- **WHEN** une colonne calculée effectue une division dont le dénominateur vaut 0
- **THEN** l'évaluateur renvoie une erreur explicite plutôt que de planter la
  génération

### Requirement: Report du total sur le suivi des paiements

Le système SHALL renseigner `documents.montant` avec le **total** calculé du document
tableau, de sorte que le suivi des paiements / impayés du patient fonctionne de
manière identique à un document mono-date.

#### Scenario: Total reporté sur le document

- **WHEN** un document tableau est enregistré avec un total de 390,000
- **THEN** `documents.montant` vaut 390,000 et le document apparaît dans les montants
  dus du patient au même titre qu'un document mono-date

#### Scenario: Date de l'acte du document tableau

- **WHEN** un document tableau regroupe des lignes datées 01/05, 02/05, 05/05, 01/06
- **THEN** `documents.acte_date` est renseignée de façon déterministe (la 1re date
  des lignes) afin de conserver un nom de fichier et un classement stables

### Requirement: Persistance des lignes sans migration destructive

Le système SHALL sérialiser les lignes saisies et les champs calculés dans la colonne
`documents.variables` (JSON) déjà existante, **sans** introduire de migration
destructive ni renommer/supprimer une colonne de production.

#### Scenario: Rechargement d'un brouillon tableau

- **WHEN** un brouillon de document tableau est enregistré puis rouvert
- **THEN** toutes ses lignes (ordre, colonnes, valeurs) sont restituées à l'identique
  depuis `documents.variables`

#### Scenario: Compatibilité ascendante des documents existants

- **WHEN** l'application ouvre une base contenant des documents mono-date antérieurs
- **THEN** ces documents se chargent et se rendent comme avant, sans être affectés par
  le nouveau format de lignes
