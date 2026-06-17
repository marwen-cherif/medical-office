## Context

Le moteur de génération (`src/doc_filler.py`) ne fait qu'une **substitution
mono-valeur** : chaque balise `<TAG>` est remplacée par une chaîne, en redistribuant
le texte entre les *runs* Word pour préserver la mise en forme (`_replace_in_para_elem`,
logique explicitement signalée comme « délicate » dans CLAUDE.md). Côté données, un
`Document` porte **un** `acte_date`, **un** `montant`, **un** `acte`, et un champ
libre `variables` (JSON des saisies). La configuration par template vit dans la table
`template_fields` (`tag`, `label`, `type`, `default_value`, `sort_order`).

Le besoin : une **note d'honoraires unique** regroupant plusieurs visites (date + acte
+ montant par ligne) avec un total, sans casser les templates mono-date existants ni la
donnée de production. Les décisions de produit déjà prises (cf. proposal) : approche
**répétition dynamique de ligne** (B) et **calculs bornés** (pas de moteur Excel libre).

Contraintes structurantes (CLAUDE.md) : Windows + Word obligatoires pour générer ;
`src/` réutilisé « sans le modifier » dans sa logique sensible ; schéma **expand-only**,
non destructif, avec bump `SCHEMA_VERSION` + migration idempotente gardée + snapshot
pré-migration ; idempotence des noms de fichiers.

## Goals / Non-Goals

**Goals:**

- Un nouveau **type de template « tableau »** détecté automatiquement, coexistant avec
  les templates « simples » inchangés.
- **Répétition dynamique** d'une ligne-modèle de tableau Word, mise en forme préservée,
  **sans toucher** `_replace_in_para_elem`.
- **Évaluateur d'expressions borné et sûr** (sans `eval`) : colonnes calculées par
  ligne (`+ - * /`, parenthèses) et agrégats document (`SUM/COUNT/AVG/MIN/MAX`).
- **Saisie ligne à ligne** (ajout/suppression/réordonnancement) avec total en direct,
  total reporté sur `document.montant` → suivi des impayés inchangé.
- **Aucune migration destructive** ; lignes persistées dans `documents.variables` (JSON).

**Non-Goals:**

- Pas de moteur de formules libre (pas d'`IF()`, pas de références croisées entre
  lignes, pas de parsing d'expressions arbitraires) — exclu volontairement (risque /
  configurabilité).
- Pas de support des tableaux Word complexes (cellules fusionnées, tableaux imbriqués
  dans la ligne-modèle) dans cette itération.
- Pas de modification du flux Mailjet ni du format de sortie (jpg/pdf).
- Pas de refonte des templates mono-date existants.

## Decisions

### D1 — Convention de balises : document vs ligne (préfixe `L_`)

Les balises de **ligne** portent le préfixe `L_` : `<L_DATE>`, `<L_ACTE>`,
`<L_MONTANT>`. Les balises **document** restent telles quelles (`<NOM>`, `<TOTAL>`,
`<NB_ACTES>`). Le nom de colonne est la balise sans préfixe, en minuscules
(`L_PRIX_UNITAIRE` → `prix_unitaire`). La regex existante `<([A-Z0-9_]+)>` matche déjà
`L_*` : la distinction se fait par préfixe, de façon **additive**.

- *Alternative écartée* : un marqueur de bloc (`<REPEAT>…</REPEAT>`) hors tableau —
  plus lourd à rendre proprement en Word et moins lisible pour l'auteur du template.

### D2 — Répétition par clonage de la ligne `<w:tr>` (réutilise le run-splitting)

`extract_placeholders` et `_fill_docx` repèrent la **ligne de tableau** (`w:tr`)
contenant ≥ 1 balise `L_*` : c'est la **ligne-modèle**. À la génération, pour N lignes
saisies, on **deepcopy** le `w:tr` modèle N fois, on insère les copies en frères après
le modèle, on remplit chaque copie via la fonction **existante**
`_replace_in_para_elem` (par paragraphe de cellule) avec le dictionnaire de la ligne,
puis on **retire le `w:tr` modèle**. Si N = 0, on retire simplement le modèle.

Conséquence clé : la duplication est **purement structurelle** (manipulation d'éléments
lxml) ; le remplissage des cellules **réutilise** la logique de redistribution de runs
sans la modifier. Le risque sur la partie « délicate » est donc évité.

- *Alternatives écartées* : (a) emplacements fixes `<DATE_1..N>` (plafonné, lignes
  vides — rejeté en discussion) ; (b) réécrire le tableau via OpenXML à la main (gros,
  fragile).

### D3 — Évaluateur borné fondé sur `ast` (jamais `eval`)

Un nouveau module (`src/formula.py`) parse l'expression avec `ast.parse(expr,
mode="eval")` et **valide la liste blanche de nœuds** :
`Expression, BinOp(Add|Sub|Mult|Div), UnaryOp(UAdd|USub), Constant(nombre),
Name(Load), Call` — `Call` uniquement vers `SUM|COUNT|AVG|MIN|MAX` avec **un** argument
`Name` (une colonne). Tout autre nœud (attribut, indexation, appel inconnu, opérateur
bit-à-bit, etc.) → **erreur explicite**, aucun code exécuté.

Deux portées d'évaluation :

- **Ligne** : `Name` = valeur numérique de la colonne de **la même** ligne ; `Call`
  interdit. Ex. `quantite * prix_unitaire`.
- **Document** : `Call(agg, colonne)` agrège sur **toutes** les lignes ; arithmétique
  autorisée sur agrégats et constantes. Ex. `SUM(montant)`, `SUM(montant) * 1,19`.

Division par dénominateur nul → erreur explicite (pas de crash). Les colonnes
référencées mais vides/non numériques → 0 en agrégat, erreur en colonne calculée selon
configuration (décision par défaut : 0, documentée).

- *Alternative écartée* : `eval` avec `__builtins__` vidé — surface de risque trop
  large, rejeté par principe (cf. CLAUDE.md sur les secrets/sécurité).

### D4 — Configuration template : extension **additive** de `template_fields`

On étend `template_fields` avec **deux colonnes nullable** :

- `scope TEXT DEFAULT 'document'` — `'document'` (balise mono-valeur, comportement
  actuel), `'line'` (colonne de ligne saisie), `'computed_line'` (colonne calculée par
  ligne), `'computed_doc'` (agrégat document).
- `expression TEXT` — l'expression pour les scopes `computed_*`, NULL sinon.

Migration **expand-only** : `_column_exists`-gardée, `SCHEMA_VERSION` bumpé, snapshot
pré-migration labellisé (exempt du prune `KEEP=10`), aucun `DROP/RENAME`. Les lignes
existantes prennent `scope='document'` par défaut → **rétro-compatibilité totale**.

- *Alternative écartée* : stocker la config tableau en JSON dans `meta`/settings (zéro
  migration) — mais éclate la config des templates en deux endroits ; les colonnes
  typées restent le foyer idiomatique et requêtable.

### D5 — Persistance des lignes dans `documents.variables` (clé réservée)

`variables` reste un objet JSON. Pour un document tableau on ajoute une **clé réservée**
`__lignes__` : `[{ "date": "...", "acte": "...", "montant": "..." }, …]` (saisies
**brutes** uniquement ; les colonnes calculées sont **recalculées** au rendu, jamais
stockées). Les balises document mono-valeur restent des clés `TAG` comme aujourd'hui.
Les documents mono-date n'ont pas `__lignes__` → chargés/rendus comme avant. Aucune
migration de données.

### D6 — Total → `montant` ; `acte_date` déterministe ; `acte` résumé

- `document.montant` = total document (par convention l'agrégat `SUM` de la colonne
  montant, ou un champ `computed_doc` désigné « total ») → alimente paiements/impayés.
- `document.acte_date` = **1re date** des lignes (déterministe) → nom de fichier et
  classement stables (idempotence des noms inchangée).
- `document.acte` = court résumé optionnel pour l'affichage liste (ex.
  « Détartrage, Composite +2 »), non normatif.

### D7 — UI : éditeur de lignes dans la fiche patient (`crm/app.py`)

Quand le template choisi est de type « tableau », l'écran de saisie affiche un
**éditeur de lignes** avec : bouton « + Ajouter une ligne », suppression par ligne,
**réordonnancement par glisser-déposer (drag)** — via `ft.ReorderableListView` (ou
`Draggable`/`DragTarget` si une cellule de saisie capture le geste), champs typés
(datepicker pour `date`, champs numériques sinon),
colonnes calculées affichées en lecture seule, et **total recalculé en direct**. La
config tableau (colonnes + champs calculés) est éditée dans l'écran de paramétrage des
variables du template.

## Risks / Trade-offs

- **Hypothèse sur la structure du tableau Word** (une seule ligne-modèle, tableau
  simple sans cellules fusionnées). → *Mitigation* : détecter et **valider** la
  ligne-modèle ; documenter la convention d'écriture du template ; message d'erreur
  clair si plusieurs lignes-modèles ou structure non supportée.
- **Clonage `w:tr` via lxml** (insertion de frères, namespaces, propriétés de ligne).
  → *Mitigation* : `deepcopy` du `w:tr` complet (conserve `w:trPr`) ; **vérifier le
  rendu réel** (pas seulement la chaîne), conformément au gotcha CLAUDE.md ; tester sur
  un `.docx` réel (Word requis).
- **Mauvaise configuration d'expression** (facture fausse silencieuse). → *Mitigation* :
  **valider l'expression à l'enregistrement** de la config (parse + essai à blanc sur un
  jeu d'exemple) ; erreurs explicites à la génération ; pas d'exécution en cas
  d'expression hors liste blanche.
- **Compat ascendante de `variables`**. → *Mitigation* : clé réservée `__lignes__`
  ignorée par le chemin mono-date ; documents existants intacts.
- **Migration sur base de production**. → *Mitigation* : colonnes nullable additives,
  migration idempotente gardée, **snapshot pré-migration** avant `connect()`/migrate,
  anti-downgrade déjà en place ; test sur copie réelle de `cabinet.db`.
- **COUNT vs montants** (formatage). → *Mitigation* : `COUNT` rendu en entier ; colonnes
  /agrégats « montant » formatés via `format_montant` selon le nom (heuristique
  MONTANT/PRIX/TARIF déjà utilisée dans `crm/generator._format_variable`).

## Migration Plan

1. **Schéma** : ajouter `scope` (DEFAULT `'document'`) et `expression` (nullable) à
   `template_fields` via un step `_migrate()` idempotent gardé par `_column_exists` ;
   bumper `SCHEMA_VERSION`.
2. **Sauvegarde** : prendre un **snapshot pré-migration** labellisé
   (`cabinet-pre-v<N>-…db`) **avant** la migration, exempt du prune `KEEP=10`.
3. **Déploiement** : nouvelle `.exe` posée à côté des données existantes ; à l'ouverture,
   migration additive transparente ; aucun document/temp existant modifié.
4. **Rollback** : l'anti-downgrade (`SchemaTooNewError`) protège déjà ; en cas de
   problème, restaurer le snapshot pré-migration. Aucune donnée détruite par la
   migration (expand-only).
5. **Validation pré-livraison** (manuelle, Word requis) : copier un `cabinet.db` de
   `backups/`, lancer la nouvelle build, vérifier qu'un patient/document/paiement
   existant se charge et se rend, puis générer un document tableau de bout en bout.

## Resolved Decisions

- **Colonnes par défaut** — *résolu* : **pas de preset**. Les colonnes d'un template
  tableau sont **entièrement configurables** par template ; aucun modèle dentaire
  pré-livré.
- **Colonnes optionnelles vides** (ex. acte sans montant) — *résolu* : un montant
  manquant/non numérique est traité comme **0** dans les agrégats (`SUM`, `AVG`, …).
- **Impression / envoi** — *résolu* : un document tableau s'imprime et s'envoie comme un
  document simple (fichier généré identique en nature), rien à changer.
- **Réordonnancement** — *résolu* : **glisser-déposer (drag)**, via
  `ft.ReorderableListView`. Le drag doit cohabiter avec les champs de saisie de la
  ligne : prévoir une **poignée de drag** dédiée si la capture du geste entre en
  conflit avec l'édition des champs.
