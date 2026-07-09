## Why

Mettre en place une structure monorepo moderne basée sur **Turborepo** et **pnpm workspaces** afin de clarifier la séparation entre le frontend React/Tauri et le backend FastAPI (sidecar), d'unifier l'expérience de développement avec une commande unique, et de nettoyer l'ancienne interface graphique **Flet** qui est obsolète et surcharge le codebase.

## What Changes

- **Migration vers pnpm** : Remplacement de npm/pip direct par un espace de travail **pnpm workspaces** pour orchestrer le frontend et le backend.
- **Introduction de Turborepo** : Ajout de `turbo.json` à la racine pour définir les pipelines de tâches (dev, build, lint, test, format).
- **Suppression complète de Flet** : Suppression de tous les fichiers liés à l'ancienne UI Flet (`crm/app.py`, `crm_app.py`, `crm_web.py`, `build-crm.bat`, `crm-desktop.spec`, `crm-web.spec`).
- **Réorganisation des dossiers** :
  - Déplacement de `ui/` vers `apps/web/`.
  - Déplacement du backend Python (moteur, FastAPI, configurations) vers `apps/api/`.
- **Automatisation du pipeline de build** : Déclaration du flux où le build de la coquille Tauri (`apps/web`) dépend du build préalable du sidecar exécutable Python (`apps/api`), le tout mis en cache par Turbo.

## Capabilities

### New Capabilities
- `monorepo-tooling`: Structure de monorepo pilotée par Turborepo et pnpm workspaces pour orchestrer le développement.

### Modified Capabilities
<!-- Aucune spécification fonctionnelle existante n'est modifiée. -->

## Impact

- Fichiers racine : Création de `package.json` (global), `pnpm-workspace.yaml`, et `turbo.json`.
- Dossier `apps/web/` (ex-`ui/`) : Mise à jour de `package.json` et des chemins d'accès relatifs vers le binaire du sidecar dans la configuration Tauri.
- Dossier `apps/api/` : Création de `package.json` (pour exposer les tâches `build:backend`, `test`, `lint`, `format` à Turbo) et réorganisation du code Python restant.
- Suppression des fichiers obsolètes liés à Flet à la racine.
