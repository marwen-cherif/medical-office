# selection-dents

## ADDED Requirements

### Requirement: Visualisation lecture seule de l'odontogramme (état clinique du patient)

Le système SHALL afficher, sur la **fiche patient** (onglet Plans & actes), un **odontogramme
anatomique** en **lecture seule** (non éditable), distinct de la grille de saisie, qui **colore
chaque dent selon son état clinique** dérivé des données cliniques **existantes** du patient. Ce
schéma SHALL s'appuyer sur un composant React dédié (librairie `react-odontogram`) et
n'introduire **aucune** nouvelle donnée, **aucune** migration de schéma ni **aucun** nouvel appel
d'API : les dents proviennent du champ `prestations.dents` déjà persisté et des données
`clinical` déjà chargées.

Le schéma SHALL être **adapté à la denture du patient** (selon l'âge, comme la saisie) :
dentition **permanente** (dents FDI 11–48) pour un adulte, dentition **temporaire** (« dents de
lait », FDI 51–85) pour un enfant. Comme la librairie numérote en interne ses dents temporaires
avec les quadrants permanents (positions), le système SHALL **convertir** les numéros FDI de
l'application (51–85) vers les identifiants attendus par la librairie, et SHALL **réafficher le
numéro FDI réel** de la dent (ex. « 55 ») dans l'**infobulle** au survol — jamais l'identifiant
interne.

Les dents concernées par un **acte réalisé** (acte isolé ou acte d'un plan) et celles concernées
par un **acte planifié** SHALL être distinguées par des **couleurs distinctes** accompagnées
d'une **légende** explicite. Cette vue SHALL être **non interactive** : un clic sur une dent ne
SHALL déclencher **aucune** sélection ni modification. La vue SHALL refléter automatiquement les
**données cliniques courantes** : toute évolution des actes du patient (ajout, modification,
suppression) SHALL se répercuter sur la colorisation sans rechargement manuel.

Toute dent qui **n'appartient pas** au schéma courant (denture mixte, ex. dent permanente chez
un enfant, ou jeton non-FDI) ne SHALL **pas** être silencieusement ignorée : elle SHALL être
**listée en texte** sous le schéma, groupée par état (réalisé / planifié), afin qu'aucune
information ne soit cachée.

L'odontogramme de **saisie** (grille numérotée native, numéros FDI permanents, bascule
Adulte/Enfant, persistance et tolérance des jetons non-FDI inchangées) n'est **pas** modifié par
cette exigence et reste le moyen d'éditer les dents d'un acte.

#### Scenario: Dents colorées selon l'état clinique (adulte)

- **WHEN** la fiche d'un patient adulte comporte un acte réalisé sur la dent 26 et un acte planifié sur la dent 36
- **THEN** l'odontogramme clinique affiche les dents 26 et 36 colorées selon des couleurs distinctes
- **AND** une légende indique la signification de chaque couleur

#### Scenario: Dents de lait colorées (enfant)

- **WHEN** la fiche d'un patient enfant comporte un acte sur la dent de lait 55
- **THEN** l'odontogramme clinique affiche la dentition temporaire avec la dent 55 colorée à sa position
- **AND** le survol de cette dent affiche le numéro FDI « 55 » en infobulle

#### Scenario: Numéro FDI consultable au survol

- **WHEN** l'utilisateur survole une dent colorée de l'odontogramme clinique
- **THEN** le numéro FDI réel de cette dent est affiché en infobulle

#### Scenario: Dent hors-schéma listée en texte

- **WHEN** la fiche d'un patient enfant comporte un acte sur une dent permanente 36 (denture mixte)
- **THEN** la dent 36 n'est pas placée sur le schéma temporaire
- **AND** elle apparaît dans la liste texte sous le schéma, dans le groupe correspondant à son état

#### Scenario: Vue non éditable

- **WHEN** l'utilisateur clique sur une dent de l'odontogramme clinique
- **THEN** aucune sélection ni modification n'est déclenchée (la vue reste en lecture seule)

#### Scenario: Mise à jour après modification d'un acte

- **WHEN** l'utilisateur ajoute un acte portant sur la dent 47
- **THEN** l'odontogramme clinique se met à jour pour colorer la dent 47 sans rechargement manuel

#### Scenario: Aucune dent renseignée

- **WHEN** aucun acte du patient ne référence de dent
- **THEN** l'odontogramme clinique s'affiche sans dent colorée (schéma neutre) et sans liste texte

#### Scenario: Saisie inchangée

- **WHEN** l'utilisateur ouvre la carte de saisie d'un acte
- **THEN** la grille numérotée d'origine est utilisée pour sélectionner les dents (numéros FDI permanents)
- **AND** l'odontogramme clinique en lecture seule n'intervient pas dans la saisie

### Requirement: Mise en évidence des dents d'un acte au survol

Le système SHALL **mettre en évidence** sur l'odontogramme clinique les dents concernées par un
acte lorsque l'utilisateur **survole** la ligne de cet acte dans la liste (actes isolés ou actes
d'un plan). La mise en évidence SHALL utiliser une **couleur distincte**, **prioritaire** sur la
couleur d'état (réalisé / planifié), et SHALL **disparaître** dès que le survol cesse. Les dents
de l'acte qui ne figurent pas sur le schéma courant (hors denture) SHALL être mises en évidence
dans la **liste texte hors-schéma**. Cette mise en évidence est **transitoire** : elle n'altère
ni les données, ni l'état coloré de base, ni le caractère non éditable de la vue.

#### Scenario: Survol d'un acte met en évidence ses dents

- **WHEN** l'utilisateur survole la ligne d'un acte portant sur les dents 26 et 27
- **THEN** les dents 26 et 27 sont mises en évidence sur le schéma avec une couleur distincte de l'état

#### Scenario: Fin du survol

- **WHEN** l'utilisateur quitte la ligne de l'acte
- **THEN** la mise en évidence disparaît et le schéma reprend les couleurs d'état (réalisé / planifié)

#### Scenario: Dent hors-schéma mise en évidence dans la liste

- **WHEN** l'utilisateur survole un acte d'un patient adulte portant sur une dent de lait 55
- **THEN** l'entrée « 55 » de la liste texte hors-schéma est mise en évidence

### Requirement: Schéma dentaire et actions maintenus visibles au défilement

Sur l'onglet Plans & actes, le système SHALL maintenir **l'odontogramme clinique et la barre
d'actions** (boutons Régler / Plan / Acte) **visibles en permanence** (épinglés en haut) lorsque
l'utilisateur fait **défiler** une longue liste d'actes. Le contenu défilant SHALL passer
**sous** cet en-tête épinglé, sans le recouvrir, et l'en-tête SHALL rester **compact** afin de ne
pas masquer la liste.

#### Scenario: En-tête épinglé au défilement

- **WHEN** l'utilisateur fait défiler une longue liste d'actes
- **THEN** l'odontogramme clinique et les boutons Régler / Plan / Acte restent visibles en haut
- **AND** la liste défile sous cet en-tête sans le recouvrir
