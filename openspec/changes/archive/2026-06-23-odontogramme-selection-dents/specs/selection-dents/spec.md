## ADDED Requirements

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
