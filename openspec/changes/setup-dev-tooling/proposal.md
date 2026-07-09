## Why

Mettre en place des outils d'analyse statique de code (linting), de formatage automatique standardisés (ESLint et Prettier pour le frontend React ; Ruff pour le backend Python) afin de garantir la cohérence stylistique, d'éviter les erreurs courantes de programmation et de faciliter la maintenance. Installer également des frameworks de tests unitaires modernes (Vitest pour le frontend ; pytest pour le backend) pour poser les bases de la validation automatisée du code.

## What Changes

- **Outils Frontend (Vite/React)** :
  - Configuration de **ESLint** avec les plugins recommandés pour React 19 et TypeScript.
  - Configuration de **Prettier** pour le formatage du code TypeScript, TSX, CSS et JSON.
  - Configuration de **Vitest** pour l'écriture et l'exécution de tests unitaires rapides côté client.
  - Ajout des scripts associés dans le fichier `ui/package.json` (`lint`, `format`, `test`).
- **Outils Backend (Python/FastAPI)** :
  - Intégration de **Ruff** pour gérer de façon ultra-rapide le linting et le formatage de l'ensemble du code Python.
  - Configuration de **pytest** (avec `pytest-asyncio` et `httpx`) pour permettre l'écriture de tests unitaires et de tests d'intégration sur les API FastAPI.
  - Création/mise à jour du fichier de configuration `pyproject.toml` à la racine pour paramétrer Ruff et pytest.
  - Ajout des dépendances de développement dans `requirements.txt`.

## Capabilities

### New Capabilities
<!-- Aucune capability fonctionnelle (métier) n'est introduite, il s'agit d'une évolution d'infrastructure et d'outillage de développement. -->

### Modified Capabilities
<!-- Aucune spécification fonctionnelle existante n'est modifiée. -->

## Impact

- `ui/package.json` et `ui/package-lock.json` : Ajout des dépendances de développement (`eslint`, `prettier`, `vitest`, etc.) et des scripts npm.
- Fichiers de configuration frontend : création ou modification de `ui/eslint.config.js`, `ui/.prettierrc`, `ui/vite.config.ts`.
- `requirements.txt` : Ajout des packages Python (`ruff`, `pytest`, `pytest-asyncio`, `httpx`).
- `pyproject.toml` à la racine : Configuration centralisée de Ruff (règles de linting et style de formatage) et de pytest.
