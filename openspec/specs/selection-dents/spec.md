# selection-dents

## Purpose

Offrir une **saisie enrichie des dents concernées** par un acte, en **notation FDI**,
combinant un **champ de saisie continu** (frappe ou dictée vocale du système, validée par
Entrée) et un **odontogramme cliquable** adulte / enfant. Le champ et l'odontogramme
partagent une **source de vérité unique** (pas de chips redondants dans le formulaire) ;
la **persistance** (chaîne séparée par des virgules dans `prestations.dents`) et la
**validation FDI non bloquante** restent inchangées. Le composant est **réutilisable** à
l'identique dans le dialogue d'acte isolé et le composer de plan de traitement, avec un
comportement **identique en mode desktop et en mode web**.

## Requirements

### Requirement: Saisie de plusieurs dents validée par Entrée (compatible dictée vocale)

Le système SHALL permettre de saisir **plusieurs dents enchaînées** dans le champ « Dents
(FDI) » — par frappe ou par **dictée vocale du système d'exploitation** (sans API micro ni
dépendance ajoutée) — séparées par un espace, une virgule, un point-virgule ou un saut de
ligne, puis de **toutes les ajouter d'un coup à l'appui sur Entrée**. Le système SHALL alors
**ajouter chaque numéro à la sélection** (les dents FDI valides apparaissant surlignées sur
l'odontogramme) et **vider le champ**. L'ajout SHALL **aussi** être déclenché par le
**bouton « + »** et par la **perte de focus** du champ (filet de sécurité). Le système ne
SHALL **pas** committer au fil de la frappe : le contenu du champ reste éditable tant
qu'Entrée (ou « + » / blur) n'est pas déclenché.

#### Scenario: Dictée de plusieurs dents puis Entrée

- **WHEN** l'utilisateur dicte « 26 27 28 » dans le champ puis appuie sur Entrée
- **THEN** les dents 26, 27 et 28 sont ajoutées en une fois et surlignées sur l'odontogramme
- **AND** le champ est vidé

#### Scenario: Saisie de plusieurs dents au clavier

- **WHEN** l'utilisateur tape « 26, 27 » puis appuie sur Entrée (ou clique « + »)
- **THEN** les dents 26 et 27 sont ajoutées à la sélection et le champ est vidé

#### Scenario: Pas de commit au fil de la frappe

- **WHEN** l'utilisateur tape « 26 27 » sans valider
- **THEN** aucune dent n'est encore ajoutée et le texte reste éditable dans le champ

### Requirement: Odontogramme cliquable adulte / enfant en notation FDI

Le système SHALL afficher, sous le champ de saisie de la carte d'acte, un **odontogramme**
(schéma dentaire) en **notation FDI**, disposé en quadrants (maxillaire en haut,
mandibulaire en bas ; côté droit du patient à gauche de l'écran). Chaque dent SHALL être
**cliquable** et **afficher en permanence son numéro FDI** (que la dent soit sélectionnée
ou non) ; la sélection se distingue visuellement (fond plein + couleur). Le système SHALL
permettre de **basculer** entre la
denture **adulte** (dents permanentes 11–18, 21–28, 31–38, 41–48) et la denture **enfant**
(dents temporaires 51–55, 61–65, 71–75, 81–85). Quand la **date de naissance** du patient
est connue, le système SHALL présélectionner la denture la plus plausible selon l'âge, tout
en restant **basculable manuellement**. L'odontogramme SHALL être un composant **natif**
(sans dépendance ni widget hors-Flet) afin d'offrir un **rendu et des clics identiques en
mode desktop et en mode web**.

#### Scenario: Sélection d'une dent par clic

- **WHEN** l'utilisateur clique sur la dent 26 de l'odontogramme
- **THEN** la dent 26 est ajoutée à la sélection et apparaît surlignée sur le schéma

#### Scenario: Désélection par re-clic

- **WHEN** l'utilisateur clique de nouveau sur une dent déjà sélectionnée
- **THEN** la dent est retirée de la sélection et n'est plus surlignée

#### Scenario: Numéro FDI toujours visible

- **WHEN** l'odontogramme est affiché
- **THEN** chaque dent affiche son numéro FDI, sélectionnée ou non
- **AND** les dents sélectionnées sont distinguées par leur fond plein

#### Scenario: Bascule denture enfant

- **WHEN** l'utilisateur bascule l'odontogramme sur la denture enfant
- **THEN** les dents temporaires (51–85) sont affichées et cliquables à la place des permanentes

#### Scenario: Défaut selon l'âge

- **WHEN** la carte d'acte s'ouvre pour un patient dont la date de naissance indique un jeune enfant
- **THEN** l'odontogramme affiche par défaut la denture enfant
- **AND** l'utilisateur peut basculer manuellement vers la denture adulte

### Requirement: Synchronisation champ ↔ odontogramme (sans chips dans le formulaire)

Le système SHALL maintenir une **source de vérité unique** pour les dents retenues, de
sorte que le **champ de saisie** (ajout) et l'**odontogramme** (affichage + sélection)
reflètent toujours le même ensemble. Le formulaire de saisie de l'acte ne SHALL **pas**
afficher de **chips** (« tags ») redondants : la sélection courante est **lue et modifiée
directement sur l'odontogramme**. Toute dent ajoutée via le champ SHALL apparaître
**surlignée** sur le schéma ; tout **clic** sur une dent du schéma SHALL **basculer** sa
sélection (ajout / retrait). Le système SHALL éviter les **doublons** dans la sélection.

#### Scenario: Une dent saisie au clavier s'allume sur le schéma

- **WHEN** l'utilisateur ajoute « 26 » via le champ de saisie et valide
- **THEN** la dent 26 est surlignée sur l'odontogramme (aucun chip n'est affiché dans le formulaire)

#### Scenario: Retrait par re-clic sur le schéma

- **WHEN** l'utilisateur re-clique sur une dent sélectionnée du schéma
- **THEN** la dent quitte la sélection et n'est plus surlignée

#### Scenario: Pas de doublon

- **WHEN** l'utilisateur ajoute « 26 » par le champ alors que la dent 26 est déjà sélectionnée
- **THEN** la sélection ne contient qu'une seule occurrence de « 26 »

### Requirement: Persistance et validation FDI inchangées

Le système SHALL conserver le **format de persistance** des dents en **chaîne séparée par
des virgules** (ex. « 26, 27 ») dans `prestations.dents`, sans migration de schéma. Les
numéros saisis SHALL être délimités par les **séparateurs** (espace, virgule,
point-virgule, saut de ligne). La validation FDI SHALL rester **facultative et non
bloquante** : un jeton non strictement FDI (ex. « 19 », numéro inexistant) SHALL rester
accepté dans la sélection et persisté tel quel. Un jeton non reconnu comme un numéro FDI
valide SHALL simplement **ne pas être reflété** sur l'odontogramme (aucune dent n'y est
surlignée — il n'est donc pas visible dans le formulaire schéma-centré), sans empêcher
l'enregistrement.

#### Scenario: Jeton non FDI toléré

- **WHEN** l'utilisateur saisit « 19 » (numéro de dent inexistant) puis valide
- **THEN** « 19 » est ajouté à la sélection et persisté tel quel
- **AND** aucune dent n'est surlignée sur l'odontogramme pour ce jeton

#### Scenario: Format de persistance conservé

- **WHEN** l'utilisateur retient les dents 26 et 27 pour un acte et l'enregistre
- **THEN** l'acte mémorise la chaîne « 26, 27 », comme avant ce changement

### Requirement: Composant réutilisable dans la carte d'acte

Le système SHALL fournir cette saisie enrichie (saisie continue + odontogramme + synchro)
via le **composant de carte d'acte commun**, de sorte qu'elle soit disponible à l'identique
dans le **dialogue d'acte isolé** et dans le **composer de plan de traitement**. Le
comportement SHALL être **identique en mode desktop et en mode web**.

#### Scenario: Disponible pour un acte isolé et dans un plan

- **WHEN** l'utilisateur ouvre l'ajout d'un acte isolé, puis compose un plan de traitement
- **THEN** la même saisie continue et le même odontogramme sont proposés dans les deux cas

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
