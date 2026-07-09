## Context

Actuellement, le projet Cabinet CRM mélange son code backend Python ( Fast API + Flet ) à la racine, tandis que l'interface React/Tauri est confinée dans le dossier `ui/`. Cette cohabitation rend l'orchestration des tâches complexe, d'autant plus que l'interface Flet originale est devenue obsolète et doit être nettoyée du projet.

## Goals / Non-Goals

**Goals:**
- Convertir le dépôt en un monorepo géré par **pnpm workspaces** et **Turborepo**.
- Supprimer complètement Flet et ses dépendances pour recentrer le backend Python sur le sidecar FastAPI.
- Séparer le code proprement dans des répertoires distincts sous `apps/`.
- Permettre le lancement de toutes les vérifications et commandes de développement depuis la racine.

**Non-Goals:**
- Modifier la logique métier du backend FastAPI ou le code React du frontend.
- Migrer la base de données SQLite vers une autre base de données.

## Decisions

### 1. Utilisation de pnpm Workspaces
Nous choisissons **pnpm** pour gérer le monorepo plutôt que npm ou yarn.
*Raison* : pnpm est plus rapide, plus économe en espace disque grâce à son stockage global partagé, et offre un excellent support natif pour les espaces de travail (workspaces).

### 2. Intégration de Turborepo
Nous ajoutons **Turborepo** à la racine du projet.
*Raison* : Turbo permet d'orchestrer le lancement des tâches en parallèle (ex: lancer le linter du front et du back simultanément) et de mettre en cache les résultats des tests et builds déjà validés.

### 3. Fichier package.json pour le Backend Python (`apps/api`)
Bien que le backend soit en Python, nous lui ajoutons un fichier `package.json`.
*Raison* : Cela permet à Turborepo d'identifier `apps/api` comme un membre de l'espace de travail à part entière et d'y exécuter des scripts npm (ex: `"test": "python -m pytest"`, `"lint": "python -m ruff check"`).

### 4. Automatisation de la copie du Sidecar
Tauri a besoin du binaire `crm-server.exe` compilé par PyInstaller pour l'inclure dans son installeur final.
*Raison* : Nous allons ajouter un script dans `apps/web/package.json` ou à la racine qui copie automatiquement le binaire de `apps/api/dist/crm-server.exe` vers `apps/web/src-tauri/binaries/crm-server-<target>.exe` juste après le build du backend, en exploitant les dépendances de tâches (`dependsOn`) de Turborepo.

## Risks / Trade-offs

- **[Risk]** : Mauvaise détection du sidecar par Tauri après le déplacement.
  - *Mitigation* : Mettre à jour les chemins des dépendances externes dans `apps/web/src-tauri/tauri.conf.json` pour pointer vers le nouvel emplacement du sidecar.
- **[Risk]** : Oubli de suppression de dépendances ou fichiers Flet.
  - *Mitigation* : Lister précisément les fichiers obsolètes et désinstaller `flet` des fichiers `requirements.txt`.
