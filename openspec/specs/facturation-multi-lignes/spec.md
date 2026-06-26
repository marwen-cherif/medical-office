# facturation-multi-lignes

## Purpose

Permettre de générer une **note d'honoraires unique** regroupant plusieurs actes d'un
patient (actes isolés et actes de plans de traitement) dans un seul document Word multi-lignes,
à partir d'un contrat de balises fixe et documenté, sans ressaisie, sans configuration de
colonnes par modèle et sans créer de paiement (le dû reste suivi sur les actes, source unique).
## Requirements
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
d'émission ; totaux `<TOTAL_DU>`, `<TOTAL_REGLE>`, `<RESTE_A_PAYER>`, `<NB_ACTES>` ; **dents
agrégées** `<DENTS>`, `<NB_DENTS>` ; **schéma dentaire** `<ODONTOGRAMME>`) et des **balises de
ligne** préfixées `L_` (`<L_DATE>`, `<L_ACTE>`, `<L_DENTS>`, `<L_NOTE>`, `<L_MONTANT>`,
`<L_REGLE>`, `<L_RESTE>`). `<DENTS>` (liste FDI agrégée) et `<NB_DENTS>` (nombre de dents
distinctes) SHALL être des balises **texte** ; `<ODONTOGRAMME>` SHALL être une balise **image**
remplacée par un schéma dentaire. La sémantique d'agrégation des dents et le rendu de l'image
relèvent de la capacité `schema-dentaire-notes`. Un modèle SHALL être considéré « note
multi-lignes » s'il contient au moins une balise de ligne `L_*`, et « simple » sinon ; les
balises document `<DENTS>`, `<NB_DENTS>` et `<ODONTOGRAMME>` SHALL être disponibles **aussi
bien** pour une note multi-lignes que pour une note simple.

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

#### Scenario: Balises dents agrégées disponibles dans le contrat

- **WHEN** l'auteur d'un modèle place `<DENTS>`, `<NB_DENTS>` et `<ODONTOGRAMME>` dans un
  modèle de note (simple ou multi-lignes)
- **THEN** ces balises sont reconnues comme des balises document du contrat et remplies à la
  génération sans configuration de colonnes, `<DENTS>`/`<NB_DENTS>` en texte et
  `<ODONTOGRAMME>` par un schéma dentaire (image)

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

### Requirement: Montant de ligne propre à la note, distinct du montant de l'acte

Le **montant de chaque ligne adossée à un acte existant** d'une note multi-lignes SHALL être **modifiable** indépendamment, avec pour **valeur par défaut** le montant de l'acte correspondant. Le montant saisi sur la ligne SHALL être **purement d'affichage** : il alimente la
balise `<L_MONTANT>` et les **totaux calculés** de la note, et ne SHALL **jamais** modifier le
montant de l'acte sous-jacent ni la dette du patient (l'acte reste la source du dû). Le montant
réglé et le reste d'une ligne adossée à un acte SHALL continuer de **refléter l'acte** (lecture
seule). À la réouverture d'un brouillon, le montant **édité** de chaque ligne SHALL être restitué.

#### Scenario: Montant de note différent du montant de l'acte
- **WHEN** un acte de 950 est retenu dans une note et l'utilisateur saisit 600 comme montant de
  sa ligne, puis génère
- **THEN** la note affiche 600 sur cette ligne et dans ses totaux, tandis que l'acte conserve son
  montant 950 et que la dette du patient reste de 950

#### Scenario: Montant de ligne par défaut repris de l'acte
- **WHEN** un acte de 950 est retenu sans que l'utilisateur n'édite le montant de sa ligne
- **THEN** la ligne affiche 950 (valeur par défaut reprise de l'acte)

#### Scenario: Édition du montant de note sans effet sur la dette
- **WHEN** l'utilisateur modifie le montant d'une ligne adossée à un acte puis génère la note
- **THEN** le montant de l'acte et le total à recouvrer du patient restent inchangés

#### Scenario: Montant édité restitué à la réouverture du brouillon
- **WHEN** un brouillon où une ligne a été éditée à 600 (acte à 950) est rouvert
- **THEN** la ligne réaffiche 600 (le montant édité), pas 950

### Requirement: Initier une note d'honoraires depuis une sélection d'actes

Le système SHALL permettre d'**initier une note d'honoraires** directement depuis la **page
Actes/Plans** d'un patient, par deux points d'entrée : (1) **sélectionner plusieurs actes**
(isolés et/ou appartenant à des plans) puis lancer « Générer une note d'honoraires » pour la
sélection, et (2) une action **« Générer une note d'honoraires »** dans le **menu d'actions
(« ⋮ ») d'une ligne d'acte**, pour cet acte unique. Le dialogue de note SHALL s'ouvrir
**pré-rempli**, le **type de modèle privilégié dépendant du nombre d'actes** :

- **plusieurs actes** → un **modèle multi-lignes** (les actes choisis **pré-cochés**, montants
  éditables, totaux calculés) ;
- **un seul acte** → un **modèle mono-valeur** **pré-rempli avec les données de l'acte**
  (libellé, montant, date, dents, note) ;
- **aucun acte** (depuis la page Actes/Plans) → un **modèle mono-valeur** vierge (note autonome).

L'utilisateur SHALL pouvoir changer le modèle proposé. Quel que soit le point d'entrée, une note
générée **depuis au moins un acte** ne SHALL **pas** créer de nouvelle dette : les actes en
restent la source (y compris une note **mono-valeur** issue d'un acte unique).

#### Scenario: Note depuis une sélection multiple d'actes
- **WHEN** l'utilisateur coche deux actes isolés et un acte d'un plan sur la page Actes/Plans,
  puis lance « Générer une note d'honoraires »
- **THEN** le dialogue s'ouvre sur un modèle multi-lignes avec ces trois actes pré-cochés, prêt à générer

#### Scenario: Note depuis la ligne d'un acte
- **WHEN** l'utilisateur ouvre le menu d'actions « ⋮ » d'un acte et choisit « Générer une note
  d'honoraires »
- **THEN** le dialogue s'ouvre sur un modèle mono-valeur dont les champs sont pré-remplis avec les
  données de cet acte (libellé, montant, date…), et aucune créance « note » n'est créée à la génération

#### Scenario: Note sans acte depuis la page Actes/Plans
- **WHEN** l'utilisateur lance « Générer une note d'honoraires » sans avoir coché d'acte
- **THEN** le dialogue s'ouvre sur un modèle mono-valeur vierge ; générer cette note autonome crée
  une créance « note » (comme une note mono-valeur classique)

#### Scenario: Génération depuis actes sans nouvelle dette
- **WHEN** une note est générée depuis des actes sélectionnés sur la page Actes/Plans (un ou plusieurs)
- **THEN** aucune créance « note » n'est créée et le total à recouvrer du patient reste celui de
  ses actes

