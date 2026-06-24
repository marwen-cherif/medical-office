## ADDED Requirements

### Requirement: Note d'honoraires multi-lignes générée depuis les actes

Le système SHALL permettre de générer une **note d'honoraires unique** regroupant
**plusieurs actes** d'un patient (actes isolés et actes de plans de traitement) dans un seul
document. Les **données de chaque acte retenu** (date, libellé, dents, montant, montant
réglé, reste) SHALL alimenter une **ligne** de la note, sans ressaisie manuelle.

#### Scenario: Regrouper plusieurs actes dans une note

- **WHEN** un patient a quatre actes saisis (détartrage 01/05, deux composites 02/05,
  couronne 05/06) et l'utilisateur ouvre « Note d'honoraires », les retient tous, puis génère
- **THEN** la note produite contient quatre lignes, chacune portant la date, le libellé et le
  montant de son acte

#### Scenario: Données de l'acte reprises sans ressaisie

- **WHEN** un acte retenu porte le libellé « Couronne céramique », un montant de 950, les
  dents « 26 » et 300 déjà réglés
- **THEN** la ligne correspondante affiche ces valeurs (libellé, montant 950, dents « 26 »,
  réglé 300, reste 650) sans que l'utilisateur ait eu à les saisir

### Requirement: Sélection des actes regroupés et pré-cochés

Le système SHALL présenter, dans le dialogue de note d'honoraires, les actes du patient
**regroupés** (actes isolés d'une part, actes par plan de traitement d'autre part) avec une
**case à cocher pré-cochée** par acte, afin que l'utilisateur retire d'un clic ceux qu'il ne
veut pas facturer. Seuls les actes **retenus** SHALL devenir des lignes de la note.

#### Scenario: Actes regroupés par origine

- **WHEN** un patient a deux actes isolés et trois actes dans le plan « Implant 26 »
- **THEN** le dialogue affiche un groupe « Actes isolés » (2) et un groupe « Implant 26 » (3),
  tous les actes pré-cochés

#### Scenario: Désélection d'un acte

- **WHEN** l'utilisateur décoche un acte avant de générer
- **THEN** la note générée ne contient pas la ligne de cet acte et les totaux excluent son
  montant

### Requirement: Ajout d'actes isolés depuis la note d'honoraires

Le système SHALL permettre d'**ajouter de nouveaux actes** directement depuis le dialogue de
note d'honoraires, via le **même formulaire que l'ajout d'acte** (sélecteur de référentiel,
libellé, montant, date, dents avec odontogramme, note). Ces actes SHALL être **créés comme
actes isolés** (`plan_id` NULL) à l'enregistrement (brouillon ou génération), de sorte qu'ils
soient **suivis dans la dette du patient** et **visibles dans l'onglet Actes/Plans**, puis
inclus comme lignes de la note. Le système ne SHALL **pas** créer de « ligne libre » non
tracée. La création SHALL être idempotente en cas de nouvelle tentative (un acte déjà créé
est mis à jour, non dupliqué).

#### Scenario: Ajout d'un acte depuis la note

- **WHEN** l'utilisateur, depuis la note, clique « + Ajouter un acte », saisit
  « Radiographie panoramique » à 60, puis génère, en plus de deux actes existants retenus
- **THEN** un acte isolé « Radiographie panoramique » (60) est créé pour le patient (visible
  dans l'onglet Actes et compté dans sa dette), et la note contient trois lignes dont le total
  dû inclut les 60

#### Scenario: Carte d'acte incomplète

- **WHEN** une carte d'ajout d'acte est laissée sans libellé
- **THEN** elle est ignorée (aucun acte créé), et une carte au montant invalide bloque la
  génération avec un message clair (aucun acte partiellement créé)

### Requirement: Contexte de variables standard prédéfini

Le système SHALL exposer aux modèles un **contrat de balises fixe et documenté**, sans
configuration de colonnes par modèle : des **balises document** (champs patient, date
d'émission, et totaux `<TOTAL_DU>`, `<TOTAL_REGLE>`, `<RESTE_A_PAYER>`, `<NB_ACTES>`) et des
**balises de ligne** préfixées `L_` (`<L_DATE>`, `<L_ACTE>`, `<L_DENTS>`, `<L_NOTE>`,
`<L_MONTANT>`, `<L_REGLE>`, `<L_RESTE>`). Un modèle SHALL être considéré « note multi-lignes »
s'il contient au moins une balise de ligne `L_*`, et « simple » sinon.

#### Scenario: Détection d'un modèle « note multi-lignes »

- **WHEN** un modèle contient au moins une balise `<L_*>` dans une cellule de tableau
- **THEN** le système le traite comme une note multi-lignes et son bloc de lignes est répété
  par les lignes retenues

#### Scenario: Modèle simple inchangé

- **WHEN** un modèle ne contient aucune balise `<L_*>`
- **THEN** il est traité comme « simple » et son rendu est identique à celui d'avant ce
  changement (une valeur par balise, aucun bloc répétable)

#### Scenario: Balises du contrat disponibles sans configuration

- **WHEN** l'auteur d'un modèle place `<L_DATE>`, `<L_ACTE>`, `<L_MONTANT>` et `<TOTAL_DU>`
- **THEN** ces balises sont remplies à la génération sans qu'aucune colonne n'ait été
  configurée pour ce modèle

### Requirement: Répétition dynamique de la ligne-modèle Word

Le moteur de remplissage SHALL **dupliquer** la ligne-modèle d'un tableau Word (la ligne
contenant les balises `L_*`) **autant de fois qu'il y a de lignes retenues**, en remplaçant
dans chaque copie les balises de ligne par les valeurs de la ligne correspondante, **en
préservant la mise en forme** de la ligne-modèle. Cette fonctionnalité SHALL être **additive**
et ne modifie pas la logique existante de redistribution de texte entre runs
(`_replace_in_para_elem`).

#### Scenario: Une ligne-modèle dupliquée par ligne

- **WHEN** une note a 4 lignes retenues et un modèle avec une seule ligne-modèle
  `<L_DATE> | <L_ACTE> | <L_MONTANT>`
- **THEN** le tableau rendu contient 4 lignes de données, chacune portant les valeurs de sa
  ligne, et la ligne-modèle d'origine n'apparaît pas avec des balises non remplies

#### Scenario: Mise en forme préservée

- **WHEN** la ligne-modèle a une mise en forme (gras, alignement, bordures)
- **THEN** chaque ligne dupliquée conserve cette mise en forme

#### Scenario: Zéro ligne retenue

- **WHEN** aucune ligne n'est retenue pour une note multi-lignes
- **THEN** le tableau ne contient aucune ligne de données (la ligne-modèle n'est pas rendue
  avec des balises non remplies)

#### Scenario: Balises document hors tableau inchangées

- **WHEN** le modèle contient aussi des balises document (`<NOM>`, `<TOTAL_DU>`, …) en dehors
  de la ligne-modèle
- **THEN** elles sont remplies une seule fois, comme aujourd'hui, sans duplication

### Requirement: Totaux calculés

Le système SHALL calculer les **totaux de la note** directement à partir des lignes retenues,
sans expression configurable : `<TOTAL_DU>` = somme des montants des lignes, `<TOTAL_REGLE>` =
somme des montants réglés (0 pour une ligne libre), `<RESTE_A_PAYER>` = `TOTAL_DU − TOTAL_REGLE`,
`<NB_ACTES>` = nombre de lignes. Les montants SHALL être formatés en style français (espace
pour les milliers, virgule décimale) cohérent avec `format_montant` ; `<NB_ACTES>` SHALL être
rendu en entier.

#### Scenario: Total dû

- **WHEN** une note regroupe des lignes de montants 80, 120, 40, 150
- **THEN** `<TOTAL_DU>` rendu vaut « 390,000 »

#### Scenario: Total réglé et reste

- **WHEN** ces mêmes lignes portent respectivement 80, 60, 0, 0 de réglé
- **THEN** `<TOTAL_REGLE>` vaut « 140,000 » et `<RESTE_A_PAYER>` vaut « 250,000 »

#### Scenario: Nombre de lignes

- **WHEN** une note contient 4 lignes
- **THEN** `<NB_ACTES>` rendu vaut « 4 »

### Requirement: Aucun paiement créé à la génération

La génération d'une note d'honoraires multi-lignes ne SHALL **jamais** créer de paiement ni
proposer d'en créer : la note **référence** les actes, dont le dû et les règlements restent
suivis sur les actes eux-mêmes (« source unique du dû », `plans-de-traitement`). Le total de
la note SHALL renseigner `documents.montant` **uniquement** comme valeur d'affichage/email, et
ne SHALL PAS apparaître comme une créance distincte des actes.

Les **nouveaux actes** ajoutés depuis la note (cf. « Ajout d'actes isolés depuis la note »)
SHALL être créés comme **actes** (`prestations`), jamais comme paiements : leur dû alimente la
dette **par l'acte** (source unique), ce qui n'est pas un double-comptage. Un acte **déjà
existant** simplement coché n'augmente pas la dette du fait de la note.

#### Scenario: Génération sans paiement

- **WHEN** l'utilisateur génère une note d'honoraires regroupant des actes
- **THEN** aucun paiement n'est créé, aucune case « créer un paiement » n'est proposée, et le
  dû du patient reste celui porté par ses actes

#### Scenario: Pas de double-comptage

- **WHEN** une note de total 390,000 est générée depuis des actes déjà suivis comme créances
- **THEN** le montant à recouvrer du patient n'augmente pas du fait de la note (il reste celui
  des actes)

### Requirement: Persistance des lignes sans migration destructive

Le système SHALL sérialiser les lignes retenues (actes et lignes libres) dans la colonne
`documents.variables` (JSON déjà existant) sous une **clé réservée** `__lignes__`, **sans**
introduire de migration de schéma ni renommer/supprimer une colonne de production. Les données
**brutes** des lignes SHALL être stockées ; les totaux et formats SHALL être **recalculés** au
rendu.

#### Scenario: Rechargement d'un brouillon multi-lignes

- **WHEN** un brouillon de note multi-lignes est enregistré puis rouvert
- **THEN** toutes ses lignes (ordre, valeurs, sélection des actes, lignes libres) sont
  restituées à l'identique depuis `documents.variables`

#### Scenario: Compatibilité ascendante des documents existants

- **WHEN** l'application ouvre une base contenant des documents mono-valeur antérieurs
- **THEN** ces documents se chargent et se rendent comme avant, sans être affectés par la clé
  `__lignes__`

#### Scenario: Date du document multi-lignes déterministe

- **WHEN** une note regroupe des lignes datées 01/05, 02/05, 05/05, 01/06
- **THEN** `documents.acte_date` est renseignée de façon déterministe (la 1re date des lignes)
  afin de conserver un nom de fichier et un classement stables
