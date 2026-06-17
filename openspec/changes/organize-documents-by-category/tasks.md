## 1. Schéma et migration (PRODUCTION — additif et gardé)

- [ ] 1.1 `crm/db.py` : dans `_SCHEMA`, ajouter `CREATE TABLE IF NOT EXISTS template_meta (template_name TEXT PRIMARY KEY, categorie TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')))`.
- [ ] 1.2 `crm/db.py` : dans `_SCHEMA`, ajouter `CREATE TABLE IF NOT EXISTS categories (nom TEXT PRIMARY KEY, couleur TEXT, icone TEXT, sort_order INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT (datetime('now')))`.
- [ ] 1.3 `crm/db.py` : dans `_migrate()`, ajouter une étape idempotente gardée par `_column_exists` — `ALTER TABLE documents ADD COLUMN categorie TEXT`.
- [ ] 1.4 `crm/db.py` : bump `SCHEMA_VERSION` de 7 à 8.
- [ ] 1.5 Vérifier qu'aucune opération destructive n'est introduite (pas de DROP/DELETE/RENAME de colonne ou table existante) et que le snapshot pré-migration de `connect()` couvre bien la montée 7 → 8.

## 2. Persistance (repo)

- [ ] 2.1 `crm/repo.py` : dataclass `Category(nom, couleur=None, icone=None, sort_order=0)` + `_row_to_category`.
- [ ] 2.2 `crm/repo.py` : `list_categories(conn)` (pour suggestions et regroupement, triées par `sort_order, nom`), `get_category(conn, nom)`, `upsert_category(conn, cat)` (création paresseuse avec couleur par défaut si absente).
- [ ] 2.3 `crm/repo.py` : `get_template_category(conn, template_name)` et `set_template_category(conn, template_name, categorie | None)` (upsert/suppression de la ligne `template_meta`, et `upsert_category` du nom si nouveau).
- [ ] 2.4 `crm/repo.py` : `rename_category(conn, ancien, nouveau, *, reclasser_documents=False)` transactionnel — renomme la ligne `categories` (couleur/icône conservées), met à jour tous les `template_meta`, et si `reclasser_documents` met à jour `documents.categorie` (le déplacement de fichiers se fait hors transaction, cf. tâche 4.x).
- [ ] 2.5 `crm/repo.py` : ajouter le champ `categorie: Optional[str] = None` au dataclass `Document` ; le lire dans `_row_to_document` avec garde `"categorie" in row.keys()` ; l'inclure dans les `INSERT`/`UPDATE` de `create_document`/`update_document`.

## 3. Conservation de la catégorie au renommage de modèle

- [ ] 3.1 `crm/templates.py::rename_template` (ou la couche app appelante) : reporter la ligne `template_meta` de l'ancien nom vers le nouveau, pour ne pas orpheliner la catégorie. Documenter que `template_fields` reste orphelin (limitation existante, hors périmètre).

## 4. Génération et routage (generator)

- [ ] 4.1 `crm/generator.py::render_document` : résoudre la catégorie via `repo.get_template_category(conn, template.name)`.
- [ ] 4.2 Calculer le dossier cible : `patient_dir(patient) / repo.slugify(categorie)` si catégorie présente, sinon `patient_dir(patient)` (racine) ; `mkdir(parents=True, exist_ok=True)`. Construire `out_path` avec `build_filename` (inchangé).
- [ ] 4.3 Renseigner `document.categorie` (libellé brut) avant `repo.update_document`.
- [ ] 4.4 (Option renommage) Fonction utilitaire de déplacement best-effort des fichiers d'une catégorie vers son nouveau sous-dossier, appelée après commit de `rename_category(..., reclasser_documents=True)` ; erreurs non bloquantes et journalisées.

## 5. Dialogues de modèle (UI)

- [ ] 5.1 `crm/app.py::_new_template_dialog` : ajouter un champ catégorie (texte libre) avec suggestions issues de `repo.list_categories()` ; à la création, appeler `repo.set_template_category`.
- [ ] 5.2 `crm/app.py::_rename_template_dialog` : afficher/éditer la catégorie courante (`repo.get_template_category`) avec les mêmes suggestions ; sauvegarder via `repo.set_template_category` ; s'assurer que le report `template_meta` (tâche 3.1) est effectif.
- [ ] 5.3 (Optionnel) éditer couleur/icône d'une catégorie depuis l'écran modèles (sinon couleur par défaut auto).

## 6. Regroupement des modèles (UI)

- [ ] 6.1 `crm/app.py::_refresh_templates` : enrichir chaque modèle de sa catégorie, regrouper par catégorie (en-tête : pastille couleur + icône + compteur), groupe « Sans catégorie » à part. Conserver la recherche existante.

## 7. Regroupement des documents — fiche patient (UI)

- [ ] 7.1 `crm/app.py` (affichage fiche patient) : regrouper les documents (`repo.list_documents`) par `documents.categorie` en sections repliables (couleur/icône + compteur), groupe « Sans catégorie » distinct, ordre récent-d'abord conservé.

## 8. Outil de renommage de catégorie (UI)

- [ ] 8.1 `crm/app.py` : action « Renommer la catégorie » (depuis l'écran modèles) appelant `repo.rename_category`, avec une case à cocher « reclasser aussi les documents déjà générés » (désactivée par défaut).

## 9. Documentation

- [ ] 9.1 Mettre à jour `CLAUDE.md` (architecture `crm/`, section données) : nouvelles tables `template_meta`/`categories`, colonne `documents.categorie`, et le fait que la catégorie est un attribut de modèle porté par l'app (pas dans le `.docx`).

## 10. Vérification manuelle (Windows + Word, base de PRODUCTION)

- [ ] 10.1 Copier une `cabinet.db` réelle depuis `backups/`, lancer le build : patients, documents et modèles existants se chargent ; vérifier qu'un snapshot pré-migration `cabinet-v7-to-v8-…db` est créé.
- [ ] 10.2 Vérifier qu'aucun fichier de `output/` n'a été déplacé ni régénéré par la mise à niveau, et que les documents existants ont `categorie` nulle (rangés à la racine).
- [ ] 10.3 Créer/éditer un modèle avec catégorie `Radiologie` (vérifier la suggestion réapparaît ensuite) ; générer un document : fichier dans `output/<patient>/radiologie/`, `documents.categorie = Radiologie`.
- [ ] 10.4 Générer depuis un modèle sans catégorie : rangement à la racine, catégorie nulle.
- [ ] 10.5 Vérifier le regroupement par catégorie (et « Sans catégorie ») dans la liste des modèles et la fiche patient, en desktop et en web.
- [ ] 10.6 Renommer une catégorie sans l'option de reclassement : les modèles suivent, les documents existants et leurs fichiers restent inchangés ; puis tester avec l'option activée.
