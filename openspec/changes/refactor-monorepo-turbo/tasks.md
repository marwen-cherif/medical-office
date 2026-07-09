## 1. Nettoyage et Préparation

- [x] 1.1 Supprimer les fichiers obsolètes liés à Flet (`crm/app.py`, `crm_app.py`, `crm_web.py`, `build-crm.bat`, `crm-desktop.spec`, `crm-web.spec`).
- [x] 1.2 Supprimer la dépendance `flet` du fichier `requirements.txt`.
- [x] 1.3 Créer la structure de répertoires `apps/` à la racine du monorepo.

## 2. Migration des Applications

- [x] 2.1 Déplacer l'application React/Tauri (`ui/`) vers le dossier `apps/web/`.
- [x] 2.2 Créer le sous-projet API dans `apps/api/` et y déplacer le dossier `crm/`, ainsi que `crm_server.py`, `crm-server.spec` et `requirements.txt`.
- [x] 2.3 Mettre à jour la configuration Tauri dans `apps/web/src-tauri/tauri.conf.json` pour ajuster les chemins du binaire externe (sidecar).

## 3. Configuration de pnpm et Turborepo

- [x] 3.1 Créer le fichier `pnpm-workspace.yaml` à la racine pour déclarer les workspaces.
- [x] 3.2 Créer le fichier `package.json` global à la racine avec les scripts de dev/test/build/lint et la dépendance vers `turbo`.
- [x] 3.3 Créer le fichier `turbo.json` à la racine avec la configuration des pipelines de tâches.
- [x] 3.4 Créer le fichier `apps/api/package.json` pour brancher le backend Python sur le pipeline de tâches de Turborepo.

## 4. Validation des Outils et Tests

- [x] 4.1 Valider l'exécution des tests en parallèle (frontend + backend) avec la commande `pnpm run test` lancée depuis la racine.
- [x] 4.2 Lancer le linter et formateur global sur tout le projet avec `pnpm run lint`.
- [x] 4.3 Valider le build de bout en bout de l'application avec `pnpm run build` depuis la racine.
