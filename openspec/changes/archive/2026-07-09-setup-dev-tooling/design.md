## Context

Actuellement, le projet Cabinet CRM ne dispose d'aucun outil standardisé de linting (analyse statique de code) ni de formatage automatique, ce qui peut mener à des écarts stylistiques ou à des erreurs de syntaxe non détectées avant l'exécution. De plus, il n'existe pas de framework de tests unitaires configuré, rendant difficile la mise en place d'une validation automatisée du code (notamment sur le frontend React et le backend FastAPI).

Cette proposition vise à combler ce manque en configurant des outils modernes et légers pour les deux parties de l'application.

## Goals / Non-Goals

**Goals:**
- Configurer **ESLint** et **Prettier** sur le frontend pour automatiser la vérification des règles de style React/TypeScript et le formatage.
- Configurer **Ruff** sur le backend Python pour assurer le linting et le formatage ultra-rapide du code.
- Mettre en place **Vitest** côté frontend pour permettre l'écriture et l'exécution rapide de tests unitaires.
- Mettre en place **pytest** (avec `pytest-asyncio` et `httpx`) pour le backend afin de tester les endpoints FastAPI et les fonctions de base de données.
- Centraliser les configurations dans les fichiers appropriés (`eslint.config.js`, `.prettierrc`, `pyproject.toml`).

**Non-Goals:**
- Écrire l'intégralité de la couverture de tests du projet (seuls des exemples de tests simples ou de configuration seront créés pour valider le bon fonctionnement).
- Mettre en place une chaîne d'intégration continue (CI/CD) complexe sur GitHub Actions (ceci pourra faire l'objet d'une autre proposition ultérieure).

## Decisions

### 1. Outils Frontend : ESLint (Flat Config) et Prettier
Nous choisissons d'utiliser la configuration moderne d'ESLint (Flat Config via `eslint.config.js` disponible depuis ESLint v9) avec le plugin officiel pour TypeScript et React. Prettier sera configuré séparément pour le formatage, et les règles de style d'ESLint en conflit avec Prettier seront désactivées via `eslint-config-prettier`.
*Raison* : C'est le standard moderne de l'écosystème React/Vite.

### 2. Framework de tests Frontend : Vitest
Nous sélectionnons **Vitest** plutôt que Jest pour le frontend. Pour permettre une bonne couverture de test (y compris sur les composants), nous incluons également la simulation du DOM via `jsdom` ainsi que l'intégration de `@testing-library/react` et `@testing-library/jest-dom`.
*Raison* : Vitest s'intègre nativement avec Vite. L'ajout de Testing Library et jsdom permet de tester le comportement réel des composants React (boutons, formulaires, modales).

### 3. Outils Backend Python : Ruff
Nous configurons **Ruff** pour remplacer à la fois `flake8`, `black`, `isort` et `autoflake`.
*Raison* : Ruff est écrit en Rust, s'exécute 10 à 100 fois plus vite que les outils traditionnels Python, et rassemble toutes les fonctionnalités de vérification et de formatage sous une commande unique. Il sera configuré via `pyproject.toml` à la racine.

### 4. Framework de tests Backend : pytest (avec base de test isolée)
Nous configurons **pytest** avec `pytest-asyncio` pour tester les routes asynchrones de FastAPI et `httpx` pour simuler des requêtes HTTP vers l'API. Pour la base de données SQLite, nous recommandons et configurons l'utilisation d'un fichier de base de données de test dédié (`data/cabinet_test.db`), recréé à blanc lors de l'exécution des tests.
*Raison* : Utiliser un fichier physique temporaire (`data/cabinet_test.db`) garantit un comportement 100% identique à la production (gestion des accès concurrents, transactions, etc.) tout en isolant totalement les données de développement ou de production contre toute altération accidentelle pendant les tests. Il est préférable à `:memory:` car SQLite en mémoire restreint le partage de connexion entre les threads du serveur FastAPI.

## Risks / Trade-offs

- **[Risk]** : Conflits de formatage initiaux importants sur le code existant.
  - *Mitigation* : Le formatage automatique via Prettier et Ruff ne sera appliqué que de façon progressive ou lors des commits, pour éviter de polluer l'historique git avec un commit massif de reformatage si le développeur le souhaite.
- **[Risk]** : Augmentation du temps de build ou d'installation des dépendances.
  - *Mitigation* : Les outils introduits sont parmi les plus rapides de l'écosystème (Ruff et Vitest sont réputés pour leur vitesse).
