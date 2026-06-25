## Context

Les modèles de documents sont **des fichiers** (`templates/*.docx`) listés par
`crm/templates.py::list_templates` ; ils n'ont **pas de ligne en base**. Seule la
configuration des variables est persistée (`template_fields`, clé `template_name`). Le
dialogue « Nouveau modèle » (`crm/app.py::_new_template_dialog`) ne saisit qu'un nom ;
« Renommer » (`_rename_template_dialog`) renomme le fichier.

La génération (`crm/generator.py::render_document`) écrit le fichier dans
`patient_dir(patient)` = `output/<nom>_<prenom>_<naissance>/`, et `crm/app.py` affiche les
documents d'un patient via `repo.list_documents` (récents d'abord).

**Contrainte majeure : l'application est en PRODUCTION.** Une base `cabinet.db` peuplée,
le dossier `output/` (notes déjà générées) et les `templates/` de l'utilisateur doivent
survivre à la mise à jour. Toute évolution est **additive et gardée** (cf. CLAUDE.md
« Data preservation »). Génération = Windows + Word uniquement (pas de CI ; tests
manuels).

## Goals / Non-Goals

**Goals:**
- Faire de la catégorie un **attribut du modèle**, saisi dans l'app (champ libre +
  suggestions), persisté en base.
- Catégorie = **entité de premier ordre** : couleur, icône, renommage global.
- Propager la catégorie : rangement `output/<patient>/<categorie>/`, regroupement des
  modèles, regroupement des documents de la fiche patient.
- **Zéro perte de données** sur une base de production : aucune colonne/table supprimée,
  aucun fichier existant déplacé ni régénéré, snapshot avant migration.

**Non-Goals:**
- Pas de balise dans le `.docx` (abandonné : la catégorie est portée par l'app).
- Pas de liste de catégories imposée : saisie libre, les suggestions ne sont
  qu'indicatives.
- Pas de filtre par catégorie dans le dialogue de génération (hors périmètre retenu).
- Pas de changement de la convention de nom de fichier (`build_filename` inchangé).
- Pas de reclassement rétroactif obligatoire des documents déjà générés (le renommage de
  catégorie peut le proposer en option, jamais d'office).

## Decisions

### Décision 1 — Modèle de données
Trois points de persistance (clé naturelle = nom du modèle / nom de catégorie) :
- `template_meta(template_name TEXT PRIMARY KEY, categorie TEXT, created_at)` — la
  catégorie courante d'un modèle (éditable). Absence de ligne = modèle sans catégorie.
- `categories(nom TEXT PRIMARY KEY, couleur TEXT, icone TEXT, sort_order INTEGER,
  created_at)` — attributs visuels et ordre d'affichage par catégorie. Créée
  paresseusement quand une nouvelle catégorie apparaît (couleur par défaut depuis une
  palette).
- `documents.categorie TEXT` — **snapshot** de la catégorie du modèle, copié à la
  génération. Sépare l'historique (figé) de la config du modèle (mutable).

*Pourquoi le snapshot sur le document* : si l'utilisateur change la catégorie d'un modèle,
les documents déjà rangés restent cohérents avec leur dossier sur disque ; la fiche
patient ne dépend pas d'une jointure vers une catégorie qui a pu bouger.

*Alternative écartée* : tout déduire à la volée du modèle. Écartée car le modèle peut être
renommé/supprimé et sa catégorie modifiée, ce qui désynchroniserait les fichiers déjà sur
disque.

### Décision 2 — Saisie libre + suggestions
Le champ catégorie des dialogues de modèle est un champ texte libre. Les suggestions
proviennent de `repo.list_categories()` (catégories déjà connues). Implémentation Flet :
champ avec menu de suggestions (ou `Dropdown` éditable / autocomplete), mais la valeur
finale reste arbitraire. Saisir une catégorie inconnue la crée (ligne `categories` avec
couleur par défaut).

### Décision 3 — Routage du fichier
`render_document` lit la catégorie du modèle via `repo.get_template_category(conn, name)`,
calcule `cat_dir = patient_dir(patient) / repo.slugify(categorie)` si présente (sinon la
racine = comportement actuel), `mkdir(parents=True, exist_ok=True)`. `build_filename`
inchangé. La colonne `documents.categorie` reçoit le libellé brut (lisible), le dossier
utilise le slug (sûr).

### Décision 4 — Schéma additif et migration (PRODUCTION)
- `categories` et `template_meta` créées via `CREATE TABLE IF NOT EXISTS` dans `_SCHEMA`
  (idempotent, sans risque sur l'existant).
- `documents.categorie` ajoutée dans `_migrate()` par `ALTER TABLE documents ADD COLUMN
  categorie TEXT`, gardée par `_column_exists` (idempotente).
- Bump `SCHEMA_VERSION` 7 → 8.
- **Aucun backfill destructif** : les documents existants gardent `categorie` nulle.
- Le snapshot pré-migration est déjà pris par `connect()` quand `disk_version <
  SCHEMA_VERSION` (`_snapshot_before_migration`).

### Décision 5 — Renommage global d'une catégorie
Opération transactionnelle `repo.rename_category(conn, ancien, nouveau)` :
1. renomme la ligne `categories` (couleur/icône conservées),
2. met à jour tous les `template_meta` portant l'ancien nom,
3. **en option (case à cocher)** : met à jour `documents.categorie` des documents déjà
   générés et déplace leurs fichiers vers le nouveau sous-dossier (best-effort, jamais par
   défaut).
Conserver aussi la cohérence du renommage de **modèle** : `templates.rename_template` doit
désormais reporter la ligne `template_meta` (aujourd'hui le renommage orpheline déjà
`template_fields` — on ne corrige pas cet existant ici, mais on évite d'introduire le même
défaut pour la catégorie).

### Décision 6 — Regroupements UI
- **Modèles** (`_refresh_templates`) : grouper par catégorie (en-tête avec pastille
  couleur + icône + compteur), modèles sans catégorie dans un groupe par défaut.
- **Fiche patient** : grouper les documents (déjà chargés) par `documents.categorie` en
  sections repliables (compteur, couleur/icône), groupe « Sans catégorie » à part ; ordre
  récent-d'abord conservé dans chaque section.

## Risks / Trade-offs

- **Renommage de modèle qui orpheline la catégorie** → catégorie perdue pour ce modèle.
  *Mitigation* : `rename_template` reporte `template_meta` (nouvelle clé).
- **Caractères invalides pour un nom de dossier dans la catégorie** (`/ : * ?` …) → échec
  `mkdir`. *Mitigation* : `repo.slugify` produit un nom sûr ; la colonne garde le libellé.
- **Collision de slug** (« Radio » vs « radio ») → même sous-dossier. *Mitigation* :
  acceptable (même catégorie logique), documenté ; les suggestions limitent les variantes.
- **Déplacement de fichiers lors d'un renommage avec option « reclasser »** → I/O risquée
  sur des fichiers de production. *Mitigation* : best-effort, désactivé par défaut, dans
  une transaction DB + déplacement après commit, erreurs non bloquantes et journalisées.
- **Production** : toute migration s'exécute sur une base peuplée. *Mitigation* : additif
  + gardé + snapshot pré-migration + test manuel sur une copie issue de `backups/`.

## Migration Plan

1. Snapshot pré-migration assuré par `connect()` (`_snapshot_before_migration`) quand
   `disk_version < SCHEMA_VERSION`.
2. `_SCHEMA` crée `categories` et `template_meta` (IF NOT EXISTS) ; `_migrate()` ajoute
   `documents.categorie` (gardé par `_column_exists`).
3. Aucun backfill : `categorie` nulle pour les documents existants ; modèles sans
   `template_meta` = sans catégorie.
4. **Rollback** : colonnes/tables additives ignorées par une version antérieure ; la garde
   anti-downgrade (`SchemaTooNewError`) empêche d'ouvrir une base v8 avec une app v7.
5. **Test manuel obligatoire** (Windows + Word) sur une copie de `cabinet.db` issue de
   `backups/` : chargement des patients/documents/modèles existants, génération avec et
   sans catégorie, vérification qu'aucun fichier existant n'a bougé.

## Open Questions

- Source des icônes : jeu d'icônes Flet (`ft.Icons`) sélectionnable, ou un petit ensemble
  prédéfini ? (tranché à l'implémentation).
- Palette de couleurs par défaut et attribution (cyclique vs choisie) — cosmétique.
- Libellé du groupe par défaut : « Sans catégorie » vs « Autres » (cosmétique).
