## ADDED Requirements

### Requirement: Cartographie de la surface UI existante

L'étude SHALL produire un **inventaire exhaustif de la couche UI actuelle** (Flet,
`crm/app.py`) : la liste des écrans, les composants récurrents et **chaque point de contact
avec le moteur** Python. Cet inventaire SHALL servir de référentiel de complétude pour
juger qu'une cible couvre 100 % de l'existant.

#### Scenario: Inventaire des écrans

- **WHEN** on consulte la cartographie
- **THEN** elle liste au minimum les écrans Tableau de bord, Patients (liste + fiche à
  onglets), Finances (paiements, dépenses), Paramétrage (modèles, modèles mail, imprimante)
  et Travaux (jobs, prestataires)
- **AND** pour chaque écran elle indique les composants UI utilisés et les fonctions du
  moteur appelées

#### Scenario: Recensement des points de contact moteur

- **WHEN** on cherche comment l'UI appelle le moteur
- **THEN** la cartographie liste les appels vers `crm/repo.py`, `crm/generator.py`,
  `crm/templates.py`, `crm/printing.py`, `src/mailer.py` et `src/doc_filler.py`
- **AND** distingue les opérations synchrones rapides des **opérations longues** (génération
  Word, envoi Mailjet, impression GDI)

### Requirement: Comparaison argumentée Flutter vs React

L'étude SHALL comparer **Flutter (Dart)** et **React** (variante desktop : Electron ou
Tauri) à l'aide d'une **grille de critères pondérés**, sans présupposer le vainqueur, et
SHALL justifier chaque note par des éléments factuels (pas de simple préférence).

#### Scenario: Grille de critères pondérés

- **WHEN** on lit la comparaison
- **THEN** elle évalue chaque option sur au minimum : qualité/fluidité d'UI,
  maintenabilité, écosystème/recrutement, intégration avec un backend Python local,
  packaging Windows compatible Word COM, courbe d'apprentissage et pérennité
- **AND** chaque critère porte une pondération explicite et une note justifiée par option

#### Scenario: Conclusion traçable

- **WHEN** la grille est renseignée
- **THEN** un score agrégé par option est calculé
- **AND** l'écart entre options et les facteurs décisifs sont explicités en clair

### Requirement: Contrat d'architecture cible frontend/backend

L'étude SHALL définir l'**architecture cible** imposée par la contrainte Windows/Word COM :
un **frontend** (Flutter ou React selon la recommandation) découplé d'un **backend Python
local** réutilisant le moteur existant **sans le modifier**, ainsi que le **contrat
d'interface (IPC)** entre les deux.

#### Scenario: Réutilisation du moteur sans modification

- **WHEN** on examine l'architecture cible
- **THEN** le moteur (`src/` et `crm/` hors `app.py`) est conservé en l'état et exposé
  derrière une interface
- **AND** aucune logique métier (génération, mail, paiements, schéma SQLite) n'est
  réécrite côté frontend

#### Scenario: Choix de canal IPC arbitré

- **WHEN** on lit la section interface
- **THEN** au moins deux canaux IPC sont comparés (par ex. HTTP localhost, WebSocket,
  JSON-RPC sur stdio)
- **AND** un canal est recommandé avec sa justification (latence, packaging, gestion des
  opérations longues et de la progression)

#### Scenario: Opérations longues et erreurs

- **WHEN** le contrat décrit la génération d'un document ou un envoi mail
- **THEN** il précise comment l'avancement est remonté au frontend (progression /
  statut asynchrone)
- **AND** comment les erreurs moteur (Word absent, COM en échec, Mailjet KO) sont
  propagées et présentées à l'utilisateur

### Requirement: Préservation des invariants existants

L'architecture cible décrite par l'étude SHALL **préserver les invariants** du produit
documentés dans `CLAUDE.md`. L'étude SHALL démontrer explicitement que la cible ne les
casse pas.

#### Scenario: Contrainte Windows / Word COM conservée

- **WHEN** on évalue la portabilité de la cible
- **THEN** l'étude confirme que la génération de documents reste pilotée par Word COM sur
  Windows
- **AND** ne propose pas de supprimer cette dépendance (hors périmètre)

#### Scenario: Préservation des données et idempotence

- **WHEN** on examine l'impact sur les données
- **THEN** l'étude confirme que `data/cabinet.db`, `output/`, `templates/` et `config.ini`
  restent la source de vérité, gérés par le backend Python
- **AND** que l'idempotence par nom de fichier et les règles de migration de schéma
  (`SCHEMA_VERSION`, `_migrate()`) restent inchangées

### Requirement: Évaluation des risques et de l'effort

L'étude SHALL recenser les **risques** de la migration et fournir une **estimation
d'effort** suffisante pour décider, avec des mesures d'atténuation pour les risques majeurs.

#### Scenario: Registre des risques

- **WHEN** on consulte la section risques
- **THEN** chaque risque porte une probabilité, un impact et une mesure d'atténuation
- **AND** les risques propres au couplage Word COM / IPC / packaging Windows y figurent

#### Scenario: Estimation d'effort exploitable

- **WHEN** on consulte l'estimation
- **THEN** l'effort est ventilé par grand lot (mise en place IPC, socle Flutter/React,
  portage par écran, packaging, recette)
- **AND** exprimé sous une forme comparable d'un lot à l'autre (fourchette ou ordre de
  grandeur assumé)

### Requirement: Plan de migration incrémental

L'étude SHALL proposer un **plan de migration progressif**, écran par écran, permettant une
**cohabitation** temporaire de l'ancienne et de la nouvelle UI plutôt qu'une bascule en un
seul bloc.

#### Scenario: Découpage par écran et premier écran pilote

- **WHEN** on lit le plan
- **THEN** il ordonne les écrans à migrer et désigne un premier écran pilote justifié
- **AND** décrit comment ancienne (Flet) et nouvelle UI coexistent pendant la transition

### Requirement: Recommandation finale motivée

L'étude SHALL se conclure par une **recommandation explicite** : migrer ou non, et le cas
échéant avec quelle techno, sous quelles conditions.

#### Scenario: Décision go / no-go traçable

- **WHEN** on lit la conclusion
- **THEN** elle énonce une décision claire (migrer / ne pas migrer) et la techno retenue
  le cas échéant
- **AND** relie cette décision aux objectifs (indépendance vis-à-vis de Flet,
  maintenabilité, qualité d'UI) et aux résultats de la grille de comparaison
