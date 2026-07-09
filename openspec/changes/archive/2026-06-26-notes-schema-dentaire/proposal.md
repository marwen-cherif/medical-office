## Why

Les notes d'honoraires affichent aujourd'hui les dents concernées uniquement en
texte, et seulement **par ligne d'acte** (`<L_DENTS>`). Le cabinet veut pouvoir
faire figurer sur la note **les numéros de dents agrégés** (le ou les actes
facturés) et surtout un **schéma odontogramme numéroté** mettant visuellement en
évidence les dents traitées — pour une note mono-acte comme pour une note
multi-actes (un seul schéma agrégeant l'ensemble des actes sélectionnés). C'est un
attendu courant des patients et des organismes pour situer les soins facturés.

## What Changes

- Ajout de **balises texte niveau document** au contrat de variables des notes :
  - `<DENTS>` : liste FDI **agrégée et dédupliquée** des dents de tous les actes
    retenus (note mono = dents de l'acte ; note multi = union des lignes), triée.
  - `<NB_DENTS>` : nombre de dents distinctes concernées.
  - La balise de ligne existante `<L_DENTS>` reste inchangée.
- Ajout d'une **balise image niveau document** `<ODONTOGRAMME>` : à la génération,
  elle est remplacée dans le `.docx` par un **schéma dentaire anatomique** (image)
  où les dents concernées sont **colorées et numérotées (FDI)**. Pour une note
  multi-actes, le schéma **agrège** les dents de tous les actes sélectionnés.
- **Nouvelle capacité de rendu serveur d'un odontogramme en image** : à partir d'un
  ensemble de numéros FDI, produire une image de schéma dentaire **sans navigateur**
  (cohérent avec la génération 100 % backend, exécutable depuis l'`.exe` figé). La
  **denture** est déterminée automatiquement d'après les FDI présents (adulte 11-48,
  enfant 51-85 ; dents mixtes ⇒ les deux dentures représentées).
- **Nouvelle capacité d'insertion d'image dans le `.docx`** : remplacer une balise
  `<…>` par une image en ligne (python-docx), en gérant les balises éclatées sur
  plusieurs runs Word — capacité **inexistante** aujourd'hui.
- Le schéma et les balises texte sont **calculés au rendu**, jamais stockés (pas de
  migration de schéma : on réutilise `Prestation.dents` et la clé `__lignes__`).
- Documentation des nouvelles balises dans l'aide du contrat de variables (UI React).

## Capabilities

### New Capabilities
- `schema-dentaire-notes`: rendu serveur d'un schéma odontogramme anatomique
  numéroté (image) à partir d'un ensemble de dents FDI, mécanisme d'insertion de
  cette image dans le `.docx` via la balise document `<ODONTOGRAMME>`, et agrégation
  des dents concernées (mono- et multi-actes) à la génération d'une note.

### Modified Capabilities
- `facturation-multi-lignes`: extension du **contrat de balises** des notes avec les
  balises document `<DENTS>`, `<NB_DENTS>` (texte agrégé des dents) et `<ODONTOGRAMME>`
  (schéma image). Le contrat reste fixe et fourni à tout modèle ; l'auteur choisit
  lesquelles afficher. `<L_DENTS>` inchangé.

## Impact

- **`src/doc_filler.py`** : nouveau chemin d'insertion d'**image** en remplacement
  d'une balise (réutilise la logique de localisation/découpe de runs) ; la
  classification des balises continue de traiter `<ODONTOGRAMME>` comme balise
  document (préfixe non `L_`).
- **Nouveau module de rendu** (ex. `src/odontogram_render.py`) : construit un SVG du
  schéma (géométrie de dents réutilisée de `react-odontogram`), le rasterise en PNG
  via **PyMuPDF/`fitz`** (déjà embarqué) ; surlignage des dents concernées + libellés
  FDI ; détection de denture.
- **`crm/generator.py`** : agrège les dents des lignes, expose `<DENTS>`/`<NB_DENTS>`,
  déclenche le rendu de l'image quand `<ODONTOGRAMME>` est présent et la passe au
  filler. Aucune écriture sur `prestations`, aucune dette créée par le schéma.
- **Dépendances** : aucune nouvelle dépendance lourde attendue (PyMuPDF et Pillow déjà
  présents) ; à valider selon la fidélité de rastérisation SVG de `fitz` (fallback
  documenté dans le design).
- **UI React** (`ui/`) : aide/documentation des balises du contrat ; **aucun**
  changement de modèle de données ni de flux de sélection des actes.
- **Données / schéma SQLite** : **aucune migration** ; schéma image et totaux dents
  recalculés au rendu (cohérent « totaux jamais stockés »). Compat ascendante totale
  des documents existants (sans `<ODONTOGRAMME>`/`<DENTS>` ⇒ rendu identique).
- **Plateforme** : rendu serveur, exécutable depuis l'`.exe` figé (Windows + Word),
  sans navigateur ; reste indisponible hors Windows comme le reste de la génération.
