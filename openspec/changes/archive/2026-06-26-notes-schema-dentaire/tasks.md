## 1. Agrégation des dents et balises texte (generator)

- [x] 1.1 Dans `crm/generator.py`, ajouter `dents_agregees(lignes)` : parse `dents` de chaque ligne (split `,;\n` façon `normalize_dents`), déduplique en conservant, trie en ordre FDI (quadrant puis position) ; renvoie la liste ordonnée. Réutiliser `repo.is_fdi_valide` / `repo.fdi_quadrant`.
- [x] 1.2 Exposer dans le dict de remplacement document `<DENTS>` = `", ".join(dents_agregees)` et `<NB_DENTS>` = `str(len(...))`, à côté de `compute_totaux`, pour note mono **et** multi-lignes.
- [x] 1.3 Vérifier l'indépendance avec `<L_DENTS>` (les dents de ligne, inchangées) et le cas « aucune dent » (`<DENTS>` vide, `<NB_DENTS>` = « 0 »).

## 2. Module de rendu serveur de l'odontogramme

- [x] 2.1 Créer `src/odontogram_render.py` et y porter la géométrie de `react-odontogram` (MIT) : `viewBox` + par dent `outlinePath` + `transform` + label, depuis `ui/node_modules/react-odontogram/dist/index.js` (et le dépôt `biomathcode/react-odontogram`). Conserver l'attribution/licence MIT.
- [x] 2.2 Construire le mapping FDI→géométrie : adulte (11-48, 8/quadrant) en direct ; temporaire (51-85, 5/quadrant) via la même conversion que `OdontogrammeClinique.tsx`, avec re-libellage FDI réel.
- [x] 2.3 Implémenter la détection de denture d'après les FDI présents (`fdi_quadrant`) : adulte / enfant / **mixte = les deux dentures** empilées dans une seule image ; FDI invalide ignoré pour le schéma.
- [x] 2.4 Composer le SVG : silhouettes de dents, **surlignage/couleur** des dents concernées, **numéro FDI** sous chaque dent, dents non concernées en aspect neutre. Garder le SVG minimal (paths + fill + stroke + text).
- [x] 2.5 Implémenter `render_png(dents) -> chemin PNG temporaire` : rasteriser le SVG via `fitz.open(stream=svg, filetype="svg")` + `get_pixmap(matrix=zoom ~3×)`, écrire un PNG temporaire. Repli documenté (svglib/cairosvg, ou labels FDI peints via Pillow) si la fidélité `fitz` déçoit.

## 3. Insertion d'image dans le `.docx` (doc_filler)

- [x] 3.1 Dans `src/doc_filler.py`, ajouter `IMAGE_TAGS = {"ODONTOGRAMME"}` et **exclure** ces balises du remplacement texte (ne pas les vider en `""`).
- [x] 3.2 Implémenter `_replace_tag_with_image(doc, tag, image_path, width)` : parcourir corps **et** cellules de tableau, localiser la balise en réutilisant la recomposition de runs de `_replace_in_para_elem` (balise éclatée gérée), vider son texte et insérer l'image via `run.add_picture(...)`.
- [x] 3.3 Gérer largeur par défaut (≈14 cm, réduite en cellule) et le cas « retirer la balise sans image » (ensemble de dents vide). No-op si la balise est absente.
- [x] 3.4 S'assurer que le chemin est **additif** : `expand_table_rows` et le remplissage texte des balises document restent inchangés ; l'insertion image s'exécute après le remplissage texte.

## 4. Branchement à la génération (generator → filler)

- [x] 4.1 Dans `crm/generator.py`, détecter via `classify_placeholders` si `ODONTOGRAMME` est présent dans le modèle ; ne rendre le PNG que dans ce cas.
- [x] 4.2 Si l'ensemble agrégé est non vide → appeler `render_png` et passer au filler une map `{ "ODONTOGRAMME": png_path }` ; sinon → demander le retrait de la balise.
- [x] 4.3 Étendre la signature de remplissage du filler pour accepter la map balise→image (paramètre optionnel, rétrocompatible) et l'appliquer après le texte.
- [x] 4.4 Supprimer le PNG temporaire après insertion ; garantir **aucune** écriture sur `prestations`/`paiements` du fait du schéma ou des dents (idempotence régénération).

## 5. Surfaçage UI (React)

- [x] 5.1 Ajouter `<DENTS>`, `<NB_DENTS>` et `<ODONTOGRAMME>` à l'aide/documentation du contrat de balises présentée à l'auteur de modèle (là où figurent `<L_*>` et les totaux), avec la consigne « placer `<ODONTOGRAMME>` dans un paragraphe dédié ».

## 7. Bloc de sélection FDI pour une note autonome

- [x] 7.1 Backend : définir `generator.DERIVED_NOTE_TAGS = {NB_DENTS, ODONTOGRAMME}` et les exclure des champs proposés (`_resolve_fields`, documents.py) et de la config (endpoint placeholders, server.py → classés « auto »). `<DENTS>` reste saisissable.
- [x] 7.2 Frontend : dans `GenerateDialog` (mode mono-valeur), rendre le champ `DENTS` via le composant `Odontogramme` (sélecteur FDI) au lieu d'un champ texte ; sérialiser la sélection en « 16, 26 » (`parseDents`/`join`), `defaultDenture` transmis.
- [x] 7.3 Vérifier le scénario note autonome (sans acte) : sélection des dents → `<DENTS>`/`<NB_DENTS>`/`<ODONTOGRAMME>` remplis ; `NB_DENTS`/`ODONTOGRAMME` non proposés ; `tsc` OK.
- [x] 7.4 Déclencher le bloc FDI dès que le modèle porte `<ODONTOGRAMME>` (champ `DENTS` synthétique dans `_resolve_fields` si absent) — un modèle mono « lettre » n'a souvent que `<ODONTOGRAMME>`.
- [x] 7.5 `_insert_images` (doc_filler) : traverser aussi les **zones de texte** du corps (`w:txbxContent`) — les modèles de lettre y placent le corps ; sans ça `<ODONTOGRAMME>` restait littéral. Vérifié par rendu Word réel sur `note_d_honoraires.docx`.

## 6. Vérification manuelle (Windows + Word)

- [x] 6.1 Préparer un modèle de test contenant `<DENTS>`, `<NB_DENTS>` et `<ODONTOGRAMME>` (en paragraphe dédié), plus une note multi-lignes avec `<L_DENTS>`.
- [x] 6.2 Générer une note **mono-acte** (dent adulte) : vérifier `<DENTS>`/`<NB_DENTS>` et un schéma adulte surligné + numéroté.
- [x] 6.3 Générer une note **multi-actes** : vérifier l'agrégation/déduplication des dents et un **schéma unique** agrégé.
- [x] 6.4 Vérifier les cas **enfant** (51-85) et **mixte** (deux dentures), puis le cas **aucune dent** (balise retirée, pas de schéma vide).
- [x] 6.5 Vérifier sur une base de production copiée que les notes/documents existants (sans ces balises) se chargent et se rendent à l'identique (compatibilité ascendante, aucune migration). — Garde-fou manuel de pré-release (nécessite la vraie `cabinet.db`) ; le mécanisme est additif/gated et le chemin « sans balise » a été vérifié (image absente ⇒ rendu inchangé). **Validé manuellement** : notes/documents existants chargés et rendus à l'identique sur copie de production.
