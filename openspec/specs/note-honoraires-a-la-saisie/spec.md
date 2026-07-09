# note-honoraires-a-la-saisie

## Purpose

Permettre, **depuis les fenêtres de création** d'un acte ou d'un plan de traitement,
d'enchaîner directement vers la **génération** (et l'**impression**) de la note d'honoraires
des actes qu'on vient de saisir, tout en conservant la possibilité de **simplement
enregistrer** sans rien générer. La génération reste celle, existante, des notes adossées aux
actes (aucune ressaisie, aucun double-comptage de la dette).

## Requirements

### Requirement: Choix d'issue à l'enregistrement d'un acte ou d'un plan

Les fenêtres de **création** « Nouvel acte » et « Nouveau plan » SHALL proposer **deux
issues** à l'enregistrement (la création d'un plan créant le plan **et** ses actes) :

1. **Enregistrer seulement** — créer le(s) acte(s) puis fermer, **sans** rien générer ;
2. **Enregistrer + générer la note** — créer le(s) acte(s) puis enchaîner vers la génération
   de la note d'honoraires.

L'issue « Enregistrer seulement » SHALL rester le **comportement par défaut** et identique à
l'existant. Le choix d'**imprimer ou non** la note ne SHALL **pas** être proposé à
l'enregistrement : il relève de la fenêtre de génération (qui expose déjà « Générer » et
« Générer et imprimer »), afin de ne pas le dupliquer. Les deux issues SHALL partager la
**même validation** des cartes d'acte (libellé obligatoire, montant valide) avant toute
création ; si la validation échoue, **aucun** acte n'est créé et **aucune** génération n'est
déclenchée. Ces issues SHALL être proposées uniquement en **création** (pas en édition d'un
acte ou d'un plan existant).

#### Scenario: Enregistrer seulement (inchangé)

- **WHEN** l'utilisateur saisit un acte et choisit « Enregistrer seulement »
- **THEN** l'acte est créé, la fenêtre se ferme, et **aucune** note n'est générée ni proposée
  (comportement actuel)

#### Scenario: Validation commune aux deux issues

- **WHEN** l'utilisateur choisit « Enregistrer + générer » avec une carte d'acte au libellé
  vide ou au montant invalide
- **THEN** la fenêtre signale l'erreur, **aucun** acte n'est créé et **aucune** génération
  n'est déclenchée

#### Scenario: Issues réservées à la création

- **WHEN** l'utilisateur **modifie** un acte ou un plan existant
- **THEN** la fenêtre n'offre que l'enregistrement simple (les issues « + générer » /
  « + générer et imprimer » ne sont pas proposées)

### Requirement: Ouverture de la note pré-remplie sur les actes nouvellement créés

Pour les issues « + générer » et « + générer et imprimer », le système SHALL ouvrir, après
création réussie du/des acte(s), la **fenêtre de génération de note d'honoraires** (mode
`note`) **pré-cochée avec exactement les actes qui viennent d'être créés**, et **eux seuls**.
Quand la création concerne un **plan**, la pré-sélection SHALL porter sur **tous les actes
créés dans ce plan**. La fenêtre de génération réutilisée SHALL être la fenêtre existante
(choix du modèle, montants de note éditables, totaux, ajout d'actes à la volée).

#### Scenario: Acte unique pré-coché

- **WHEN** l'utilisateur crée un acte « Détartrage » via « Enregistrer + générer »
- **THEN** la fenêtre de note s'ouvre avec « Détartrage » pré-coché, et la note générée
  contient la ligne de cet acte

#### Scenario: Tous les actes d'un nouveau plan pré-cochés

- **WHEN** l'utilisateur crée un plan « Implant 26 » contenant trois actes via
  « Enregistrer + générer »
- **THEN** la fenêtre de note s'ouvre avec ces **trois** actes pré-cochés (et aucun autre acte
  préexistant du patient coché par défaut)

### Requirement: Choix générer / imprimer dans la fenêtre de note

Le choix « générer » ou « générer et imprimer » SHALL se faire **dans la fenêtre de génération**
(qui expose déjà les deux actions), et non à l'enregistrement. Lorsqu'un **seul** modèle de note
d'honoraires est disponible, il SHALL être **pré-sélectionné** afin que l'utilisateur puisse
valider rapidement. Aucune des deux actions ne SHALL être déclenchée automatiquement (cf.
« Aucune génération ni impression silencieuse »).

#### Scenario: Modèle unique pré-sélectionné

- **WHEN** l'utilisateur arrive sur la fenêtre de note depuis « Enregistrer + générer » et qu'un
  unique modèle de note existe
- **THEN** la fenêtre s'ouvre avec ce modèle pré-sélectionné et les actes créés pré-cochés,
  prête à « Générer » ou « Générer et imprimer » au choix

#### Scenario: Choix d'imprimer ou non

- **WHEN** la fenêtre de note est ouverte
- **THEN** l'utilisateur peut cliquer « Générer » (sans imprimer) ou « Générer et imprimer »,
  selon son choix

### Requirement: Aucune génération ni impression silencieuse

Le système ne SHALL **jamais** générer ni imprimer une note sans une **confirmation explicite**
de l'utilisateur dans la fenêtre de génération. L'enchaînement depuis la saisie SHALL seulement
**ouvrir** la fenêtre pré-remplie ; la génération (et l'éventuelle impression) ne se déclenche
qu'au clic sur « Générer » / « Générer et imprimer ».

#### Scenario: Confirmation requise

- **WHEN** l'utilisateur choisit « Enregistrer + générer la note »
- **THEN** rien n'est généré ni envoyé à l'imprimante tant qu'il n'a pas validé (« Générer » ou
  « Générer et imprimer ») dans la fenêtre de note

### Requirement: Actes conservés si la note est abandonnée

Le(s) acte(s) déjà créé(s) SHALL **rester enregistré(s)** et visibles dans l'onglet
Actes/Plans si, après l'enchaînement, l'utilisateur **ferme ou annule** la fenêtre de
génération sans générer (la création de l'acte et la génération de la note sont deux étapes
distinctes ; seule la note est abandonnée).

#### Scenario: Abandon de la note après création de l'acte

- **WHEN** l'utilisateur crée un acte via « Enregistrer + générer » puis ferme la fenêtre de
  note sans générer
- **THEN** l'acte reste créé et listé dans l'onglet Actes/Plans, et aucune note n'a été
  produite

### Requirement: Réutilisation des règles de dette existantes

L'enchaînement SHALL réutiliser la génération de note **adossée aux actes** : la note produite
**référence** les actes créés sans créer de paiement supplémentaire, conformément à la règle
« source unique du dû ». La dette du patient SHALL provenir des **actes** créés à la saisie,
**pas** de la note ; générer la note ne SHALL **pas** ajouter de créance distincte ni
double-compter le montant.

#### Scenario: Pas de double-comptage à l'enchaînement

- **WHEN** l'utilisateur crée un acte de 150 via « Enregistrer + générer » puis génère la note
- **THEN** la dette du patient augmente de **150 une seule fois** (portée par l'acte), et la
  note ne crée **aucune** créance distincte
