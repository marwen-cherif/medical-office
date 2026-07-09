# socle-react-sidecar

## Purpose

Établir le socle de la migration de l'UI Flet vers React : un backend Python (`crm/server.py`,
FastAPI) qui expose le moteur existant (`src/` et `crm/` hors `app.py`) sous forme de façade de
services, communique avec un frontend React via un transport local sécurisé (HTTP 127.0.0.1,
port éphémère, jeton de session), gère les opérations longues sans blocage (progression SSE,
erreurs structurées), et reste empaqueté en un exécutable double-cliquable (coquille Tauri +
sidecar PyInstaller). Le tout préserve les invariants documentés (Word COM, backup+migrations,
idempotence par nom de fichier) et permet la cohabitation Flet/React sans divergence de données.

## Requirements

### Requirement: Façade de services backend réutilisant le moteur

Le backend (`crm/server.py`, FastAPI) SHALL exposer une **façade de services** — une opération
par cas d'usage UI — qui réutilise le moteur existant (`src/` et `crm/` hors `app.py`) **sans
modifier ses signatures publiques**. Aucune logique métier (génération, mail, paiements, schéma
SQLite, règles d'idempotence) ne SHALL être réimplémentée côté frontend.

#### Scenario: Lecture servie par le moteur

- **WHEN** le frontend demande la liste des modèles de documents
- **THEN** le backend appelle `crm/templates.list_templates` et renvoie le résultat en JSON
- **AND** la connexion SQLite est ouverte et possédée par le backend (jamais exposée au
  frontend)

#### Scenario: Aucune règle métier côté frontend

- **WHEN** on examine une opération d'écriture (créer un acte, régler en cascade)
- **THEN** le calcul et la persistance sont effectués par les fonctions `crm/repo.py`
  existantes via la façade
- **AND** le frontend ne fait qu'appeler l'opération et afficher le résultat

### Requirement: Transport local sécurisé

Le backend SHALL communiquer avec le frontend en **HTTP sur 127.0.0.1**, sur un **port
éphémère** choisi au démarrage et transmis au frontend, et SHALL exiger un **jeton de session**
partagé au lancement.

#### Scenario: Découverte du port au démarrage

- **WHEN** le backend démarre
- **THEN** il se lie à un port libre sur l'interface loopback uniquement
- **AND** le port et le jeton de session sont transmis au frontend avant le premier appel

#### Scenario: Requête non authentifiée rejetée

- **WHEN** une requête arrive sans le jeton de session attendu
- **THEN** le backend la rejette avec un statut d'erreur d'authentification

### Requirement: Opérations longues — progression et erreurs structurées

Les opérations longues (génération de document, envoi d'email, impression) SHALL être exécutées
sans bloquer la requête HTTP, remonter leur **progression** via un canal d'événements, et
propager les erreurs moteur en **codes structurés** présentés à l'utilisateur en français.

#### Scenario: Suivi de progression d'une génération

- **WHEN** le frontend demande la génération d'un document
- **THEN** le backend répond immédiatement avec un identifiant de tâche
- **AND** la progression et l'achèvement (ou l'échec) sont diffusés sur un canal d'événements
  (SSE)

#### Scenario: Erreur moteur propagée

- **WHEN** Microsoft Word est indisponible lors d'une génération
- **THEN** le backend renvoie un code d'erreur structuré (par ex. `WORD_UNAVAILABLE`)
- **AND** le frontend affiche un message d'erreur lisible en français

### Requirement: Écran pilote Paramétrage à parité fonctionnelle

Le frontend React SHALL couvrir l'écran **Paramétrage** — modèles de documents, modèles
d'email, imprimante, catalogue d'actes — à **parité fonctionnelle** avec l'implémentation Flet
existante (libellés français, mêmes opérations).

#### Scenario: Gestion des modèles de documents

- **WHEN** l'utilisateur ouvre Paramétrage › Modèles
- **THEN** il peut lister, créer, renommer, supprimer un modèle, configurer ses variables et
  l'ouvrir dans Word
- **AND** la catégorie d'un modèle peut être assignée comme dans la version Flet

#### Scenario: Gestion du catalogue d'actes

- **WHEN** l'utilisateur ouvre Paramétrage › Actes
- **THEN** il peut lister (avec recherche et inclusion des inactifs), créer, modifier,
  activer/désactiver un acte tarifé

#### Scenario: Test de l'imprimante

- **WHEN** l'utilisateur choisit une imprimante et lance un test
- **THEN** le backend exécute `crm/printing.print_test_page` et renvoie le résultat (succès ou
  code d'erreur)

### Requirement: Cohabitation Flet / React sans divergence de données

L'ancienne UI Flet (`crm/app.py`) SHALL rester lançable pendant la transition, et les deux UI
SHALL partager le **même backend et la même base de données**, de sorte qu'aucune divergence de
données ne soit possible.

#### Scenario: Modification visible des deux côtés

- **WHEN** un acte est créé via le frontend React
- **THEN** il est visible dans l'UI Flet (et inversement), car les deux lisent la même base via
  le même moteur

#### Scenario: Flet reste opérationnel

- **WHEN** on lance l'application Flet pendant la cohabitation
- **THEN** elle fonctionne sans régression (aucun écran retiré dans ce périmètre)

### Requirement: Packaging Windows en deux process

Le livrable SHALL rester un **exécutable double-cliquable** : coquille **Tauri** embarquant le
**sidecar Python** empaqueté par PyInstaller (`externalBin`), avec les données de l'utilisateur
conservées **à côté de l'exécutable**.

#### Scenario: Cycle de vie du sidecar

- **WHEN** l'utilisateur lance l'exécutable Tauri
- **THEN** la coquille démarre le sidecar Python, découvre son port et ouvre l'UI
- **AND** la fermeture de l'application arrête le sidecar

#### Scenario: Données à côté de l'exe

- **WHEN** l'application est installée et lancée
- **THEN** `data/cabinet.db`, `output/`, `templates/` et `config.ini` résident à côté de
  l'exécutable, comme avec le build Flet actuel

### Requirement: Préservation des invariants existants

L'architecture cible SHALL préserver les invariants documentés dans `CLAUDE.md`, qui restent
portés par le **backend Python inchangé**.

#### Scenario: Génération toujours pilotée par Word COM

- **WHEN** un document est généré
- **THEN** la génération reste pilotée par Word via COM dans le sidecar Windows
- **AND** la dépendance Word COM n'est pas supprimée

#### Scenario: Backup et migrations au démarrage du backend

- **WHEN** le backend démarre et ouvre la base
- **THEN** un backup pré-migration est pris (rotation `KEEP=10`) avant l'application des
  migrations
- **AND** `db.connect` applique `_migrate()` et refuse une base plus récente que l'application
  (`SchemaTooNewError`)

#### Scenario: Idempotence par nom de fichier conservée

- **WHEN** une génération est relancée pour un document déjà produit
- **THEN** la logique d'idempotence par nom de fichier (`crm/generator.build_filename`)
  court-circuite la régénération, exactement comme aujourd'hui
