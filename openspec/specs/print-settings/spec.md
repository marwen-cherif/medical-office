# print-settings Specification

## Purpose
TBD - created by archiving change print-settings-per-type. Update Purpose after archive.
## Requirements
### Requirement: Réglages d'impression par type de document

Le système SHALL permettre de définir, pour chaque type de document (identifié par le
nom de son modèle, ex. `demande_radio`, `examen_biologique`, `facture`), un **format
papier** parmi un ensemble pris en charge (au minimum A4 et A5) et un **mode couleur**
parmi { Couleur, Noir & blanc }. Ces réglages SHALL être configurables depuis
**Paramétrage › Imprimante**.

#### Scenario: Définir le format et la couleur d'un type

- **WHEN** l'utilisateur ouvre Paramétrage › Imprimante, choisit le format « A5 » et le
  mode « Noir & blanc » pour le type « demande_radio », puis enregistre
- **THEN** le système mémorise ce réglage pour le type « demande_radio »
- **AND** un message confirme l'enregistrement

#### Scenario: Type sans réglage explicite

- **WHEN** aucun réglage n'a été défini pour un type de document
- **THEN** le système n'impose ni format ni couleur pour ce type
- **AND** Paramétrage › Imprimante affiche ce type avec la valeur « Par défaut de
  l'imprimante »

### Requirement: Persistance des réglages sans migration de schéma

Le système SHALL mémoriser les réglages d'impression par type dans la table `meta`
(via `repo.get_setting`/`set_setting`), sans aucune modification du schéma SQLite ni
migration. Les réglages SHALL survivre au redémarrage de l'application et aux mises à jour
de l'exécutable, au même titre que le choix de l'imprimante (`printer_name`).

#### Scenario: Réglages conservés après redémarrage

- **WHEN** l'utilisateur a enregistré des réglages par type puis redémarre l'application
- **THEN** les réglages précédemment enregistrés sont rechargés et appliqués

#### Scenario: Aucune migration de schéma

- **WHEN** la fonctionnalité est déployée sur une base de données de production existante
- **THEN** `SCHEMA_VERSION` reste inchangé et aucune table ni colonne n'est créée,
  modifiée ou supprimée

### Requirement: Application silencieuse des réglages à l'impression

Lorsque l'utilisateur imprime un document, le système SHALL résoudre le type du document,
puis appliquer automatiquement le format papier et le mode couleur mémorisés pour ce type,
**sans afficher de boîte de dialogue**. Si le type ne possède pas de réglage, le système
SHALL imprimer avec les réglages par défaut de l'imprimante (comportement antérieur).

#### Scenario: Facture imprimée en A4

- **WHEN** le type « facture » est réglé sur A4 / Noir & blanc et l'utilisateur clique sur
  « Imprimer » pour une facture
- **THEN** le document est envoyé à l'imprimante au format A4 en noir & blanc
- **AND** aucune boîte de dialogue de réglages n'est affichée

#### Scenario: Demande de radio imprimée en A5

- **WHEN** le type « demande_radio » est réglé sur A5 et l'utilisateur clique sur
  « Imprimer » pour une demande de radio
- **THEN** le document est envoyé à l'imprimante au format A5
- **AND** aucune boîte de dialogue de réglages n'est affichée

#### Scenario: Repli sur le défaut de l'imprimante

- **WHEN** l'utilisateur imprime un document dont le type n'a aucun réglage défini
- **THEN** le document est imprimé avec le format et la couleur par défaut de
  l'imprimante, comme avant l'introduction de la fonctionnalité

### Requirement: Tolérance aux capacités du pilote d'imprimante

Le système SHALL appliquer le format et la couleur via le DEVMODE de l'imprimante. Si le
pilote ne prend pas en charge un réglage demandé, l'impression SHALL néanmoins aboutir en
retombant sur le comportement par défaut du pilote, sans faire échouer l'envoi.

#### Scenario: Format non pris en charge par l'imprimante

- **WHEN** un type est réglé sur un format que l'imprimante cible ne propose pas
- **THEN** le document est tout de même imprimé (le pilote utilise son format par défaut)
- **AND** aucune exception n'interrompt l'impression

