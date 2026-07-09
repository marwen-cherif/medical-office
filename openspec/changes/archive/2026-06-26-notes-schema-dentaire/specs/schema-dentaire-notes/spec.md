## ADDED Requirements

### Requirement: Agrégation des dents concernées d'une note

À la génération d'une note d'honoraires, le système SHALL calculer l'**ensemble agrégé des
dents** concernées à partir des dents FDI de **tous les actes retenus** : pour une note
mono-acte, les dents de l'acte ; pour une note multi-actes, l'**union** des dents de toutes les
lignes retenues. Cet ensemble SHALL être **dédupliqué** et **ordonné de façon déterministe**
(ordre FDI croissant par quadrant). Il alimente les balises `<DENTS>`, `<NB_DENTS>` et le schéma
`<ODONTOGRAMME>`. Cette agrégation SHALL être purement de **lecture** : aucune écriture sur
`prestations`, aucune dette, aucune modification du champ `dents` des actes.

#### Scenario: Union des dents en multi-actes

- **WHEN** une note retient trois actes portant respectivement les dents « 16 », « 26, 27 » et
  « 36 »
- **THEN** l'ensemble agrégé des dents est { 16, 26, 27, 36 } et `<NB_DENTS>` vaut « 4 »

#### Scenario: Déduplication des dents communes

- **WHEN** deux actes retenus portent tous deux la dent « 26 »
- **THEN** « 26 » n'apparaît qu'une fois dans l'ensemble agrégé et n'est comptée qu'une fois

#### Scenario: Note mono-acte

- **WHEN** une note simple est générée pour un acte unique portant la dent « 26 »
- **THEN** l'ensemble agrégé vaut { 26 } et alimente `<DENTS>`, `<NB_DENTS>` et le schéma

#### Scenario: Aucune dent renseignée

- **WHEN** aucun acte retenu ne porte de dent
- **THEN** l'ensemble agrégé est vide, `<NB_DENTS>` vaut « 0 » et `<DENTS>` est rendu vide

### Requirement: Balises texte des dents agrégées

Le système SHALL exposer la balise document `<DENTS>` = liste FDI agrégée et formatée des dents
concernées (séparateur « , » cohérent avec la saisie, ex. « 16, 26, 27 ») et `<NB_DENTS>` =
nombre entier de dents distinctes. Ces balises SHALL être disponibles pour toute note (simple ou
multi-lignes), remplies une seule fois au niveau document, et indépendantes de la balise de ligne
`<L_DENTS>` (qui reste les dents d'une ligne).

#### Scenario: Rendu de la liste agrégée

- **WHEN** l'ensemble agrégé est { 16, 26, 27 }
- **THEN** `<DENTS>` rendu vaut « 16, 26, 27 » et `<NB_DENTS>` vaut « 3 »

#### Scenario: Indépendance vis-à-vis de `<L_DENTS>`

- **WHEN** un modèle multi-lignes place `<DENTS>` dans une ligne de totaux et `<L_DENTS>` dans
  la ligne-modèle
- **THEN** `<L_DENTS>` affiche les dents propres à chaque ligne tandis que `<DENTS>` affiche
  l'ensemble agrégé une seule fois

### Requirement: Rendu serveur d'un schéma odontogramme anatomique

Le système SHALL produire, **côté serveur et sans navigateur**, une **image de schéma dentaire
anatomique** à partir d'un ensemble de dents FDI : les dents **concernées** SHALL être
**colorées/surlignées** et chaque dent SHALL porter son **numéro FDI**. La **denture** SHALL
être déterminée automatiquement d'après les FDI présents : adulte (11-48), enfant/temporaire
(51-85), et **mixte** ⇒ les **deux dentures** représentées. Le rendu SHALL s'exécuter depuis
l'exécutable figé (Windows + Word) en s'appuyant sur des bibliothèques **déjà embarquées**
(PyMuPDF/`fitz`, Pillow), sans dépendance à un navigateur ni à l'UI React.

#### Scenario: Schéma adulte surligné et numéroté

- **WHEN** l'ensemble agrégé vaut { 16, 26, 27 } (toutes adultes)
- **THEN** le schéma rendu représente la denture adulte, surligne les dents 16, 26 et 27, et
  affiche le numéro FDI de chaque dent

#### Scenario: Schéma enfant pour dents temporaires

- **WHEN** l'ensemble agrégé vaut { 55, 61 } (dents temporaires)
- **THEN** le schéma rendu représente la denture temporaire et surligne les dents 55 et 61

#### Scenario: Dentition mixte

- **WHEN** l'ensemble agrégé mêle des dents adultes et temporaires (ex. { 16, 55 })
- **THEN** le schéma représente les deux dentures et surligne 16 (adulte) et 55 (temporaire)

#### Scenario: Seules les dents concernées sont surlignées

- **WHEN** un schéma est rendu pour l'ensemble { 26 }
- **THEN** seule la dent 26 est mise en évidence, les autres dents restant en aspect neutre

### Requirement: Insertion d'une image en remplacement d'une balise dans le `.docx`

Le moteur de remplissage SHALL prendre en charge le **remplacement d'une balise document par une
image en ligne** dans le `.docx` (capacité nouvelle, additive). Pour la balise `<ODONTOGRAMME>`,
le moteur SHALL localiser la balise — y compris lorsqu'elle est **éclatée sur plusieurs runs
Word** — retirer son texte et insérer l'**image du schéma** à son emplacement, en préservant la
mise en forme environnante. Cette capacité SHALL être **additive** et ne pas altérer la logique
existante de remplacement de texte ni la répétition des lignes-modèles.

#### Scenario: Balise image remplacée par le schéma

- **WHEN** un modèle contient `<ODONTOGRAMME>` dans un paragraphe et une note avec des dents est
  générée
- **THEN** la balise est remplacée par l'image du schéma dentaire à cet emplacement, sans texte
  résiduel `<ODONTOGRAMME>`

#### Scenario: Balise éclatée sur plusieurs runs

- **WHEN** la balise `<ODONTOGRAMME>` est répartie sur plusieurs runs Word (mise en forme
  partielle)
- **THEN** elle est tout de même détectée et remplacée par l'image, sans laisser de fragment de
  balise

#### Scenario: Modèle sans balise schéma inchangé

- **WHEN** un modèle ne contient pas `<ODONTOGRAMME>`
- **THEN** aucune image n'est insérée et le rendu est identique à celui d'avant ce changement

#### Scenario: Balise dans une zone de texte (modèle « lettre »)

- **WHEN** la balise `<ODONTOGRAMME>` est placée dans une **zone de texte** Word
  (`w:txbxContent`), cas fréquent des modèles de lettre mis en page
- **THEN** elle est tout de même remplacée par l'image (la passe d'insertion traverse les
  zones de texte du corps, comme le remplissage texte), sans laisser de balise littérale

### Requirement: Schéma agrégé unique pour une note multi-actes

Pour une note **multi-actes**, la balise `<ODONTOGRAMME>` SHALL produire un **schéma unique**
agrégeant les dents de **tous les actes retenus** (et non un schéma par ligne). Le schéma utilise
l'ensemble agrégé des dents de la note.

#### Scenario: Un seul schéma pour plusieurs actes

- **WHEN** une note multi-actes retient des actes sur les dents 16, 26, 27 et 36 et le modèle
  contient une balise `<ODONTOGRAMME>`
- **THEN** la note rendue contient **un seul** schéma mettant en évidence 16, 26, 27 et 36

### Requirement: Schéma calculé au rendu, sans persistance ni effet sur la dette

L'ensemble agrégé des dents et l'image du schéma SHALL être **calculés au rendu** et **jamais
stockés** : **aucune migration** du schéma SQLite, réutilisation de `Prestation.dents` et de la
clé `__lignes__` existante. La génération du schéma et des balises de dents ne SHALL créer ni
modifier **aucun** `paiement` ou `prestation`. Les documents générés **sans** ces balises SHALL
se charger et se rendre à l'identique (compatibilité ascendante). Lorsque la balise
`<ODONTOGRAMME>` est présente mais qu'**aucune dent** n'est concernée, le système SHALL retirer
la balise sans insérer d'image (pas de schéma vide trompeur).

#### Scenario: Aucune écriture en base au rendu

- **WHEN** une note avec `<ODONTOGRAMME>`, `<DENTS>` et `<NB_DENTS>` est générée puis régénérée
- **THEN** aucune ligne `prestations` n'est modifiée, aucune créance/paiement n'est créé du fait
  du schéma ou des dents, et le résultat est identique entre les deux générations

#### Scenario: Compatibilité ascendante des documents existants

- **WHEN** l'application rouvre une base contenant des notes antérieures sans ces balises
- **THEN** ces documents se chargent et se rendent comme avant, sans schéma ni balise dents

#### Scenario: Balise schéma sans dent concernée

- **WHEN** un modèle contient `<ODONTOGRAMME>` mais que la note ne porte aucune dent
- **THEN** la balise est retirée et aucune image n'est insérée

### Requirement: Bloc de sélection FDI pour une note autonome

Le système SHALL présenter, dans le dialogue de génération d'une note **mono-valeur** (autonome,
sans acte rattaché) dont le modèle porte la balise `<ODONTOGRAMME>` **ou** `<DENTS>`, un **bloc
de sélection de dents FDI** (odontogramme interactif) à la place d'un champ texte. Lorsque le
modèle porte `<ODONTOGRAMME>` sans champ `<DENTS>` explicite, le système SHALL ajouter un champ
`DENTS` (rendu par ce bloc) afin que les dents puissent être saisies. La sélection SHALL
alimenter `<DENTS>` (liste FDI), et par dérivation `<NB_DENTS>` et `<ODONTOGRAMME>`. Le système
ne SHALL **pas** proposer à la saisie les balises **dérivées** `<NB_DENTS>` et `<ODONTOGRAMME>`
(calculées à la génération), tandis que `<DENTS>` reste saisissable via ce bloc.

#### Scenario: Sélection des dents sur une note autonome

- **WHEN** l'utilisateur génère une note autonome dont le modèle contient `<DENTS>` et
  sélectionne les dents 16 et 26 dans le bloc odontogramme
- **THEN** la note rendue affiche `<DENTS>` = « 16, 26 », `<NB_DENTS>` = « 2 » et un schéma
  mettant en évidence 16 et 26

#### Scenario: Schéma sans champ DENTS explicite

- **WHEN** un modèle de note mono-valeur contient `<ODONTOGRAMME>` mais **aucune** balise
  `<DENTS>`
- **THEN** le dialogue de génération propose tout de même le bloc de sélection FDI (champ
  `DENTS` ajouté), permettant de choisir les dents qui alimentent le schéma

#### Scenario: Balises dérivées non saisies

- **WHEN** un modèle de note mono-valeur contient `<DENTS>`, `<NB_DENTS>` et `<ODONTOGRAMME>`
- **THEN** seule `<DENTS>` est proposée (via le bloc de sélection FDI) ; `<NB_DENTS>` et
  `<ODONTOGRAMME>` ne sont pas demandées à la saisie
