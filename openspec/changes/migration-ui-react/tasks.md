> Périmètre : **walking skeleton + écran pilote Paramétrage** (lots L0+L1+L2 de l'étude).
> Le moteur (`src/` + `crm/` hors `app.py`) est **réutilisé sans modification**. Flet reste
> lançable (cohabitation). Génération/impression exigent **Windows + Word** → recette manuelle.

## 1. Socle backend FastAPI (L0)

- [x] 1.1 Ajouter les dépendances de dev backend (`fastapi`, serveur ASGI `uvicorn`, support
      SSE) à `requirements.txt`
- [x] 1.2 Créer `crm/server.py` : application FastAPI ; au démarrage, **backup pré-migration**
      (`backup.backup_db`) **puis** ouverture via `crm/db.connect` (le backend possède la
      connexion et les données)
- [x] 1.3 Démarrage sécurisé : liaison **loopback 127.0.0.1 sur port éphémère**, génération
      d'un **jeton de session**, middleware d'authentification rejetant toute requête sans jeton
- [x] 1.4 Routes de la façade **Paramétrage** réutilisant le moteur sans le modifier :
      `templates.*` (list/create/rename/delete/openInWord/placeholders/fields), `categories.*`,
      `mailTemplates.*`, `printers.list`, `settings.*`, `actes.*`
- [x] 1.5 Canal des **opérations longues** : route renvoyant `202` + identifiant de tâche, flux
      **SSE** `GET /events/{jobId}`, exécution en **pool de threads** (COM initialisé dans le
      worker) ; câbler `printers.test` → `crm/printing.print_test_page`
- [x] 1.6 Mapper les erreurs moteur en **codes structurés** (`WORD_UNAVAILABLE`,
      `PRINTER_NOT_FOUND`, `PRINT_FAILED`, `TEMPLATE_INVALID`, `SCHEMA_TOO_NEW`,
      `VALIDATION_ERROR`) avec schéma de réponse d'erreur
- [x] 1.7 Vérifier que **`/openapi.json`** décrit toutes les opérations Paramétrage (contrat
      pour le client TS)

## 2. Socle frontend React (L1)

- [x] 2.1 Initialiser `ui/` : **Vite + React 19 + TypeScript**, versions **épinglées**
      (compat Vite ↔ Tauri ↔ Tailwind v4 ↔ React 19 ↔ shadcn CLI)
- [x] 2.2 Configurer **Tailwind v4** (`@theme`) + **shadcn/ui** (composants copiés dans `ui/`),
      reprendre la **palette** de `crm/app.py`
- [x] 2.3 Générer le **client TypeScript** depuis l'OpenAPI et configurer **TanStack Query**
      (injection du jeton + URL de base découverts au lancement)
- [x] 2.4 Construire le **shell** : `NavigationRail` + routing, thème, toasts (Sonner)
- [x] 2.5 Intégrer les composants transverses nécessaires au pilote : `Tabs`, `Table`,
      `Dialog`, `Form` (react-hook-form + zod), `Badge`, `Select`

## 3. Écran pilote Paramétrage — UI (L2)

- [x] 3.1 Sous-onglet **Modèles de documents** : lister, créer, renommer, supprimer, configurer
      les variables, ouvrir dans Word, assigner une catégorie
- [x] 3.2 Sous-onglet **Modèles d'email** : lister, créer/modifier, supprimer, définir par
      défaut
- [x] 3.3 Sous-onglet **Imprimante** : choix de l'imprimante + format/couleur, enregistrer,
      **test** (avec progression et code d'erreur le cas échéant)
- [x] 3.4 Sous-onglet **Actes** : lister (recherche + inclusion des inactifs), créer, modifier,
      activer/désactiver
- [x] 3.5 Présentation des **erreurs** (codes backend → messages français) et des **états de
      progression** des opérations longues

## 4. Packaging Windows 2 process (L2)

- [x] 4.1 Empaqueter le **sidecar** via **PyInstaller** (réutiliser `crm-desktop.spec`) en
      binaire externe — `crm-server.spec` ; `dist/crm-server.exe` **construit et testé** (le
      binaire gelé imprime bien le handshake et sert `/api/health`)
- [x] 4.2 Configurer **Tauri `externalBin`** : démarrage/arrêt du sidecar, **transmission
      port + jeton**, ouverture de la WebView2 — `ui/src-tauri/` (`tauri.conf.json`,
      `src/main.rs`) ; config validée par `tauri info` ; **`cargo build` à faire sur poste
      outillé** (Rust + MSVC absents ici)
- [x] 4.3 Vérifier que les données restent **à côté de l'exe** (`data/`, `output/`,
      `templates/`, `config.ini`) — via `crm/db.app_dir()` (inchangé)
- [x] 4.4 Produire un **exécutable double-cliquable** et documenter le cycle de vie du process
      + la découverte du port — `build-crm-react.bat` + `ui/README.md` ; **bundle NSIS final
      gated sur Rust/MSVC** (cf. `recette.md`)

## 5. Cohabitation & préservation des invariants

- [x] 5.1 Vérifier que **Flet (`crm/app.py`) reste lançable** et partage backend + base : une
      modification faite via React est visible dans Flet (et inversement)
- [x] 5.2 Vérifier **backup pré-migration + migrations + anti-downgrade** (`SchemaTooNewError`)
      au démarrage du backend
- [x] 5.3 Vérifier la **idempotence par nom de fichier** (génération relancée court-circuitée)
- [x] 5.4 Vérifier que **Word COM** reste utilisé et que les **secrets `config.ini`** ne sont
      jamais transmis au frontend

## 6. Recette du pilote (Windows + Word — manuelle)

- [ ] 6.1 **Recette de parité** de Paramétrage contre Flet (référentiel `cartographie.md` de
      l'étude) sur une **vraie DB** copiée de `backups/`
- [ ] 6.2 Mesurer la **latence ressentie** des listes et acter le **seuil de recette**
- [ ] 6.3 Acter le **go/no-go intermédiaire** avant le portage des écrans denses (Patients, …)
