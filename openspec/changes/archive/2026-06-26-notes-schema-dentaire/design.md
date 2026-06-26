## Context

Les notes d'honoraires reposent sur un **contrat de balises fixe** (capability
`facturation-multi-lignes`) rempli par `crm/generator.py` et injecté dans le `.docx` par
`src/doc_filler.py`. Aujourd'hui :

- Les dents d'un acte sont stockées en chaîne FDI sur `Prestation.dents` (`crm/repo.py`,
  ~L2412), normalisées par `normalize_dents` (~L2323). La convention FDI (adulte 11-48,
  enfant 51-85) et les helpers `is_fdi_valide` / `fdi_quadrant` existent déjà (~L2350-2381).
- `crm/generator.py` projette chaque acte en ligne brute (`prestation_to_ligne`, ~L233),
  calcule les totaux (`compute_totaux`, ~L260) et formate les `<L_*>` (`_ligne_to_row_repl`,
  ~L289). `<L_DENTS>` y est déjà alimenté **par ligne**.
- `src/doc_filler.py` détecte les balises via `_PLACEHOLDER_RE = <([A-Z0-9_]+)>` (~L72),
  les classe document/ligne par préfixe `L_` (`classify_placeholders`, ~L135), remplit le
  **texte** (run-splitting `_replace_in_para_elem`) et duplique la ligne-modèle
  (`expand_table_rows`, ~L176). **Aucune insertion d'image n'existe.**
- `fitz`/PyMuPDF est déjà embarqué (`src/pdf_to_jpg.py`), Pillow aussi (`crm/printing.py`).
- Côté React, `OdontogrammeClinique.tsx` rend un schéma anatomique via `react-odontogram`
  (SVG, MIT) ; la lib contient les `outlinePath`/`transform`/`viewBox` et labels par dent,
  et la conversion FDI↔denture temporaire y est déjà gérée.

On veut ajouter : balises texte **document** `<DENTS>`/`<NB_DENTS>` (dents agrégées) et une
balise **image** `<ODONTOGRAMME>` remplacée par un schéma dentaire anatomique numéroté, le
tout calculé au rendu, sans navigateur, sans migration, exécutable depuis l'`.exe` figé.

## Goals / Non-Goals

**Goals:**

- Exposer `<DENTS>` (liste FDI agrégée, dédupliquée, ordonnée) et `<NB_DENTS>` (entier) comme
  balises document de toute note (simple ou multi-lignes).
- Rendre, côté serveur et sans navigateur, un **schéma odontogramme anatomique** (image) à
  partir d'un ensemble de dents FDI : dents concernées colorées, numéro FDI sous chaque dent,
  denture auto-détectée (adulte / enfant / mixte = les deux).
- Ajouter à `src/doc_filler.py` un chemin d'**insertion d'image** en remplacement d'une balise
  document, gérant les balises éclatées sur plusieurs runs, **additif** au remplacement texte.
- Réutiliser les bibliothèques déjà embarquées (`fitz`, Pillow) et la géométrie MIT de
  `react-odontogram` ; aucune migration SQLite, aucune écriture sur `prestations`/`paiements`.

**Non-Goals:**

- **Pas** de schéma par ligne (`<L_ODONTOGRAMME>`) ni de mini-schéma dans le tableau (décidé :
  document seulement). Un seul schéma agrégé par note.
- **Pas** de sélection/édition manuelle des dents du schéma : il dérive des actes retenus.
- **Pas** de couleurs par état clinique (réalisé/planifié) sur le schéma imprimé : un seul
  style « dent concernée » (l'odontogramme clinique à l'écran garde, lui, ses états).
- **Pas** de rendu via navigateur headless ni de dépendance à l'UI React au moment de la
  génération.
- **Pas** de migration de schéma SQLite ni de stockage de l'image/des totaux dents.

## Decisions

### D1 — Rendu serveur = SVG composé en Python, rasterisé par `fitz`

Un nouveau module `src/odontogram_render.py` construit un **SVG** du schéma puis le rasterise
en **PNG** via PyMuPDF (`fitz.open(stream=svg, filetype="svg")` → `page.get_pixmap(matrix=…)`
avec un zoom ~3× pour la netteté impression). Choix : `fitz` est déjà embarqué et rasterise du
SVG « simple » (paths, `fill`, `stroke`, `text`) ; Pillow seul ne sait pas interpréter des
chemins SVG. On garde le SVG volontairement simple (pas de gradient/filtre) pour rester dans le
sous-ensemble bien supporté. **Fallback documenté** si la fidélité `fitz` est insuffisante :
`svglib`+`reportlab` ou `cairosvg` (dépendance à ajouter alors, à éviter si possible).

### D2 — Géométrie portée depuis `react-odontogram` (MIT)

On **porte** dans un module de données Python la géométrie anatomique de la lib : `viewBox`,
et par dent son `outlinePath` (silhouette) + `transform` (position) + `label`. Source :
`ui/node_modules/react-odontogram/dist/index.js` (et le dépôt GitHub `biomathcode/react-odontogram`
pour des chaînes lisibles). On conserve l'attribution/licence MIT. Le schéma imprimé n'a pas
besoin d'être **pixel-identique** à l'écran : on vise la même silhouette anatomique et la même
disposition par quadrant. La géométrie est **figée** (copiée), drift acceptable.

### D3 — Mapping FDI ↔ géométrie + détection de denture

- Adulte : quadrants 1-4, dents 11-48 (8 par quadrant) → mapping direct vers la géométrie.
- Enfant/temporaire : quadrants 5-8, dents 51-85 (5 par quadrant) → on réutilise la **même
  conversion** que `OdontogrammeClinique.tsx` (placer les 5 dents temporaires sur les
  emplacements correspondants), avec **re-libellage FDI réel** (51…85) sous chaque dent.
- Denture détectée d'après les FDI présents (via `fdi_quadrant`) : quadrants 1-4 seuls ⇒
  adulte ; 5-8 seuls ⇒ enfant ; **mélange ⇒ les deux dentures** rendues (deux blocs empilés
  dans une seule image). Helper réutilisé : `is_fdi_valide` / `fdi_quadrant` (`crm/repo.py`).
- Un FDI invalide/inconnu est ignoré pour le schéma (tolérant, cohérent avec D10 « validation
  FDI non bloquante ») mais reste présent dans le texte `<DENTS>` tel que saisi.

### D4 — Agrégation des dents (generator)

Dans `crm/generator.py`, une fonction `dents_agregees(lignes)` (ou sur l'acte mono) :
1. parse chaque `dents` de ligne via la logique de `normalize_dents` (split `,;\n`),
2. **déduplique en conservant** puis **trie en ordre FDI** (par quadrant puis position),
3. renvoie la liste ordonnée → `<DENTS>` = `", ".join(...)`, `<NB_DENTS>` = `str(len(...))`.
Ces balises sont ajoutées au dict de remplacement document, à côté de `compute_totaux`. Coût
nul si le modèle ne les contient pas (mais elles sont toujours fournies, comme le reste du
contrat). Aucune écriture base.

### D5 — Déclenchement du rendu image piloté par la présence de la balise

Le rendu PNG n'est effectué **que si** `ODONTOGRAMME` figure dans les balises document du
modèle (obtenu via `classify_placeholders`). Le générateur :
1. calcule l'ensemble agrégé (D4) ;
2. si non vide → `odontogram_render.render_png(dents) -> chemin PNG temporaire` ;
3. passe au filler une **map balise→image** `{ "ODONTOGRAMME": png_path }` ;
4. si l'ensemble est vide → ne rend rien et signale au filler de **retirer** la balise
   (pas de schéma vide trompeur, cf. spec).
Le PNG est un fichier **temporaire** (comme le PDF intermédiaire actuel), supprimé après
insertion ; rien n'est stocké.

### D6 — Insertion image dans le `.docx` (`src/doc_filler.py`)

Nouvelle constante `IMAGE_TAGS = {"ODONTOGRAMME"}` et nouveau chemin d'insertion :
- les balises image sont **exclues** du remplacement texte (ne pas les vider en `""`) ;
- une fonction `_replace_tag_with_image(doc, tag, image_path, width)` parcourt paragraphes
  (corps **et** cellules de tableau, comme `extract_placeholders`), localise la balise — en
  **réutilisant la logique de recomposition des runs** de `_replace_in_para_elem` pour gérer
  une balise éclatée —, vide le texte de la balise et insère l'image via
  `run.add_picture(image_path, width=Emu/Cm)` (python-docx) à l'emplacement du run ;
- largeur par défaut raisonnable (ex. ~14 cm, ou ~6 cm en cellule) ; documenter de placer
  `<ODONTOGRAMME>` dans un **paragraphe dédié** pour éviter tout débordement ;
- si `tag` absent → no-op ; si demandé « retirer » (ensemble vide) → vider le texte sans image.
Le chemin est **additif** : `expand_table_rows` et `_replace_in_para_elem` restent inchangés ;
l'insertion image s'exécute après le remplissage texte des balises document.

### D7 — Surfaçage UI (React)

Documenter les nouvelles balises (`<DENTS>`, `<NB_DENTS>`, `<ODONTOGRAMME>`) dans l'aide du
contrat de variables affichée à l'auteur de modèle (là où sont listées `<L_*>` et les totaux).
Pour une note **adossée aux actes**, le schéma se déduit des dents des actes déjà transmis :
**aucun** changement des payloads (`selected_prestation_ids`, `__lignes__`, `montants_notes`).

Pour une note **autonome** (mono-valeur, sans acte), les dents proviennent de la variable
`DENTS` : le dialogue de génération rend alors le champ `DENTS` via le **bloc de sélection FDI**
(composant `Odontogramme` réutilisé de la carte d'acte), sérialisé en « 16, 26 ». Les balises
**dérivées** `<NB_DENTS>` et `<ODONTOGRAMME>` sont exclues des champs saisis via
`generator.DERIVED_NOTE_TAGS` (filtré dans `_resolve_fields` et l'endpoint placeholders), de
sorte qu'elles ne soient jamais demandées à l'utilisateur (calculées à la génération).

## Risks / Trade-offs

- **Fidélité de rastérisation SVG par `fitz`.** MuPDF ne couvre pas tout le SVG (gradients,
  filtres, certains `text`). *Mitigation* : SVG minimal (paths + fill + stroke + text simple),
  test de rendu réel ; *fallback* `svglib`/`cairosvg` documenté si nécessaire (au prix d'une
  dépendance). Le numéro FDI peut, en repli, être « peint » par-dessus le PNG via Pillow plutôt
  qu'en `<text>` SVG si le rendu texte de `fitz` déçoit.
- **Insertion image dans un run éclaté.** Comme pour le texte, c'est délicat ; on réutilise la
  localisation existante mais `add_picture` doit cibler un run réel. *Mitigation* : tester le
  rendu via Word COM (pas seulement la structure python-docx), gérer le cas balise seule dans
  son paragraphe en priorité (cas recommandé et le plus simple).
- **Géométrie copiée (drift).** La géométrie figée diverge si la lib évolue. *Acceptable* :
  écran et imprimé n'ont pas à être pixel-identiques ; on garde l'attribution MIT.
- **Mapping dents temporaires.** 5 dents/quadrant côté FDI vs 8 emplacements de géométrie :
  risque de placement/libellé erroné. *Mitigation* : réutiliser la conversion déjà validée de
  `OdontogrammeClinique.tsx` et vérifier visuellement enfant + mixte.
- **Largeur d'image fixe.** Une balise placée dans une petite cellule peut déborder.
  *Mitigation* : largeur réduite en contexte cellule + consigne « paragraphe dédié ».
- **Plateforme.** Le rendu reste Windows-only (intégré au pipeline de génération Word) ; pas de
  CI possible — vérification manuelle sur une base de production copiée, comme les autres
  évolutions de génération.
- **Performance.** Une rastérisation par note : négligeable ; ne s'exécute que si la balise est
  présente.
