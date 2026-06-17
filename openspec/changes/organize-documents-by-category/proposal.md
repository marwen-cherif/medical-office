## Why

Aujourd'hui, tous les documents générés pour un patient atterrissent en vrac dans
un unique dossier `output/<nom>_<prenom>_<naissance>/`, et la liste des modèles est une
simple liste à plat. Au fil des visites, ce dossier mélange notes d'honoraires,
demandes de radio, ordonnances et examens biologiques, ce qui rend la recherche pénible.
Le cabinet veut **catégoriser ses modèles de documents** et voir cette catégorie se
propager partout : rangement des fichiers, organisation des modèles, et fiche patient.

## What Changes

- **La catégorie devient un attribut du modèle**, saisi dans l'application : le
  dialogue « Nouveau modèle » / « Renommer le modèle » gagne un **champ catégorie en
  texte libre** (à côté du nom). La catégorie n'est PAS écrite dans le `.docx`.
- **Suggestions** : le champ catégorie est libre mais propose les catégories déjà
  utilisées (saisie assistée, sans liste figée) pour éviter les doublons par faute de
  frappe.
- **La catégorie est une entité de premier ordre** : elle porte une **couleur** et une
  **icône** (repérage visuel), et peut être **renommée partout d'un coup**.
- **Rangement des documents générés** : un document est écrit dans
  `output/<patient>/<categorie>/` au lieu de la racine du dossier patient. La catégorie
  est **figée sur le document** à la génération (nouvelle colonne `documents.categorie`)
  pour rester stable même si la catégorie du modèle change ensuite.
- **Organisation des modèles** : l'écran Paramétrage › Modèles **regroupe les modèles
  par catégorie**, avec pastille de couleur/icône.
- **Fiche patient** : les documents sont **regroupés par catégorie** (sections repliables
  avec compteur et couleur/icône).
- **Rétro-compatible** : un modèle sans catégorie continue de fonctionner (document rangé
  à la racine du dossier patient) ; les documents déjà générés ne sont ni déplacés ni
  régénérés.

## Capabilities

### New Capabilities
- `document-categories`: catégorie en tant qu'attribut de modèle (texte libre, avec
  suggestions, couleur, icône, renommage global) et sa propagation au rangement des
  documents générés, à l'organisation des modèles et au regroupement des documents de la
  fiche patient.

### Modified Capabilities
<!-- Aucune capability existante : openspec/specs/ est vide. -->

## Impact

- **Code** :
  - `crm/db.py` — nouvelles tables `template_meta` (modèle → catégorie) et `categories`
    (couleur/icône/ordre par catégorie) via `CREATE TABLE IF NOT EXISTS`; colonne
    additive `documents.categorie`; bump `SCHEMA_VERSION` (7 → 8) + étape de migration
    idempotente.
  - `crm/repo.py` — CRUD catégories (`Category` dataclass), association modèle↔catégorie,
    liste des catégories pour suggestions, renommage global ; champ `categorie` sur
    `Document`.
  - `crm/generator.py` — résolution de la catégorie du modèle à la génération, routage du
    fichier dans `patient_dir(patient)/<slug(categorie)>/`, écriture de
    `document.categorie`.
  - `crm/app.py` — champ catégorie + suggestions dans les dialogues de modèle ;
    regroupement/couleur dans la liste des modèles ; regroupement par catégorie (sections
    repliables) dans la fiche patient ; outil de renommage de catégorie.
- **Données** : nouvelles tables + colonne additive nullable. Les documents existants
  (catégorie nulle) restent à la racine du dossier patient ; aucun fichier déjà généré
  n'est déplacé ni régénéré. Conforme aux règles de préservation des données de
  CLAUDE.md (expand-only, migration gardée, snapshot pré-migration).
- **Modèles** : aucun `.docx` à modifier ; la catégorie est portée par l'application.
