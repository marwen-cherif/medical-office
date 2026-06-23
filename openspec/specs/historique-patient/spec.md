# historique-patient

## Purpose

Journaliser de façon **structurée et best-effort** les événements significatifs d'une fiche
patient dans `audit_log` (horodatage, `patient_id`, type d'action, `detail` JSON), puis les
restituer dans l'onglet « Historique » de la fiche : flux antichronologique groupé par jour,
filtrage par catégorie, et détail avant/après des mises à jour. La migration est **additive**
et **rétrocompatible** avec les lignes de journal antérieures.

## Requirements

### Requirement: Enregistrement structuré des événements par patient

Le système SHALL enregistrer chaque événement significatif survenu sur une fiche patient
dans le journal d'audit (`audit_log`), avec au minimum : un horodatage, l'identifiant du
patient concerné (`patient_id`), un type d'action, et un `detail` structuré sérialisé en
JSON. L'enregistrement SHALL être **best-effort** : un échec d'écriture du journal ne SHALL
jamais faire échouer ni annuler l'action métier qui l'a déclenché.

#### Scenario: Journalisation rattachée au patient

- **WHEN** une action métier modifie la fiche d'un patient
- **THEN** une ligne est ajoutée à `audit_log` avec le `patient_id` du patient, le type
  d'action et un `detail` JSON
- **AND** cette ligne est récupérable en filtrant le journal sur ce `patient_id`

#### Scenario: Échec de journalisation sans impact métier

- **WHEN** l'écriture dans `audit_log` échoue (erreur SQLite)
- **THEN** l'action métier déclenchante se termine normalement
- **AND** aucune erreur n'est remontée à l'utilisateur du fait du journal

### Requirement: Couverture des événements de la fiche

Le système SHALL journaliser au minimum les événements suivants, chacun avec un type
d'action distinct et un `detail` JSON pertinent : création de fiche patient ; mise à jour
de fiche patient ; création, édition et suppression d'un plan de traitement ; ajout,
édition et suppression d'un acte (prestation) ; règlement d'un acte ; génération d'un
document (avec son type/modèle) ; génération d'une note d'honoraires ; envoi d'un document
par email.

#### Scenario: Génération de document journalisée avec le modèle

- **WHEN** un document est généré pour un patient
- **THEN** un événement de type « document généré » est enregistré
- **AND** son `detail` JSON contient le type/modèle du document généré

#### Scenario: Ajout d'acte journalisé

- **WHEN** un acte (prestation) est ajouté à un patient
- **THEN** un événement « acte ajouté » est enregistré avec, dans le `detail`, le libellé
  de l'acte et, le cas échéant, les dents concernées

### Requirement: Capture des champs modifiés lors d'une mise à jour de fiche

Lorsqu'une fiche patient est mise à jour, le système SHALL déterminer la liste des champs
réellement modifiés et SHALL enregistrer, pour chacun, sa valeur **avant** et sa valeur
**après** dans le `detail` JSON de l'événement. Un champ inchangé NE SHALL PAS apparaître
dans le `detail`.

#### Scenario: Seuls les champs modifiés sont consignés

- **WHEN** l'utilisateur change uniquement le téléphone d'un patient et enregistre
- **THEN** l'événement « fiche modifiée » consigne le champ « téléphone » avec son ancienne
  et sa nouvelle valeur
- **AND** ne consigne aucun autre champ

#### Scenario: Aucune modification effective

- **WHEN** l'utilisateur enregistre la fiche sans avoir changé aucune valeur
- **THEN** aucun champ avant/après n'est consigné dans le `detail`

### Requirement: Affichage chronologique de l'historique

L'onglet « Historique » de la fiche patient SHALL afficher les événements du patient en
ordre antichronologique (le plus récent en premier), **groupés par jour**. Chaque entrée
SHALL présenter une icône et un libellé lisible correspondant à son type d'action, ainsi
que son heure.

#### Scenario: Flux antichronologique groupé par jour

- **WHEN** l'utilisateur ouvre l'onglet « Historique » d'un patient ayant des événements
- **THEN** les événements sont regroupés par jour (ex. « Aujourd'hui », « Hier », date)
- **AND** au sein de chaque jour, le plus récent est affiché en premier
- **AND** chaque entrée affiche une icône, un libellé lisible et l'heure

#### Scenario: Patient sans historique

- **WHEN** un patient n'a aucun événement journalisé
- **THEN** l'onglet « Historique » affiche un message indiquant l'absence d'historique

### Requirement: Filtrage de l'historique par catégorie

L'onglet « Historique » SHALL proposer des filtres permettant de restreindre l'affichage à
une catégorie d'événements (au minimum : Fiche, Plans, Actes, Documents, Règlements), ainsi
qu'une option pour tout afficher.

#### Scenario: Filtrer sur une catégorie

- **WHEN** l'utilisateur active le filtre « Documents »
- **THEN** seuls les événements liés aux documents (génération, note d'honoraires, envoi)
  sont affichés
- **AND** sélectionner « Tous » réaffiche l'ensemble des événements

### Requirement: Affichage du détail avant/après des mises à jour

L'onglet « Historique » SHALL afficher, sous une entrée de mise à jour comportant des
champs modifiés, chaque champ impacté avec sa valeur avant et sa valeur après.

#### Scenario: Détail des modifications affiché

- **WHEN** l'historique contient un événement « fiche modifiée » avec des champs modifiés
- **THEN** l'entrée affiche chaque champ impacté sous la forme « champ : avant → après »
- **AND** par exemple « téléphone : — → 06 12 34 56 78 »

### Requirement: Rétrocompatibilité du journal existant

La migration du journal d'audit SHALL être additive et SHALL préserver les lignes
`audit_log` antérieures. Les lignes sans `patient_id` (antérieures à la migration) NE
SHALL PAS empêcher l'affichage ; elles n'apparaissent simplement dans l'historique d'aucun
patient. Une valeur de `detail` non-JSON (ancienne) SHALL être tolérée à l'affichage sans
provoquer d'erreur.

#### Scenario: Anciennes lignes préservées

- **WHEN** la base est migrée vers la nouvelle version du journal
- **THEN** les lignes `audit_log` existantes sont conservées
- **AND** celles sans `patient_id` ne sont rattachées à aucune fiche patient

#### Scenario: Detail non structuré toléré

- **WHEN** l'historique rencontre une ligne dont le `detail` n'est pas un JSON valide
- **THEN** l'entrée est affichée sans détail avant/après et sans erreur
