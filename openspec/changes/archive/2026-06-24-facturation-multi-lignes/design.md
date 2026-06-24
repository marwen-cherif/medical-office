## Context

Le moteur de génération (`src/doc_filler.py`) ne fait qu'une **substitution mono-valeur** :
chaque balise `<TAG>` est remplacée par une chaîne, en redistribuant le texte entre les
*runs* Word pour préserver la mise en forme (`_replace_in_para_elem`, signalée « délicate »
dans CLAUDE.md). `_fill_docx` parcourt corps, zones de texte et en-têtes/pieds, **mais pas
les cellules de tableau**. Côté données, un `Document` porte **un** `acte_date`, **un**
`montant`, **un** `acte`, et un champ libre `variables` (JSON). Le pont `crm/generator.py`
construit `repl` depuis la fiche patient (`_patient_replacements`) et les saisies
(`_format_variable`, qui formate déjà dates et montants), puis appelle
`WordSession.fill_and_export_pdf`.

Depuis la conception initiale, `plans-de-traitement` a introduit la table `prestations`
(actes réalisés) : chaque `Prestation` porte `libelle`, `montant`, `montant_regle`,
`statut`, `date_acte`, `dents`, `note`, `plan_id` (NULL = acte isolé) et des propriétés
dérivées `reste` / `facturable`. `repo.list_prestations(conn, patient_id, plan_id=…)`
liste les actes isolés ou ceux d'un plan ; `repo.plan_totaux` agrège (dû, encaissé, reste).
**Règle structurante** : `plans-de-traitement` impose **« source unique du dû »** — générer
un document ne crée **jamais** de paiement ; le dû est porté exclusivement par les actes.

Le besoin : une **note d'honoraires unique** regroupant **plusieurs actes** (isolés + plans),
déjà saisis **ou ajoutés à la volée**, sans ressaisie, sans casser les modèles mono-valeur
existants ni la donnée de production. Décisions produit (cf. proposal) : lignes **alimentées
par les actes** (existants cochés + nouveaux actes isolés créés depuis la note),
**contexte de variables standard prédéfini** façon Mailjet, **totaux calculés en Python**
(pas d'évaluateur de formules).

Contraintes (CLAUDE.md) : Windows + Word obligatoires pour générer ; `src/` réutilisé
« sans le modifier » dans sa logique sensible ; schéma **expand-only** non destructif ;
idempotence des noms de fichiers.

## Goals / Non-Goals

**Goals:**

- **Note multi-lignes générée depuis les actes** : sélection des actes du patient (isolés +
  plans), pré-cochés et regroupés, leurs données alimentant les lignes de la note.
- **Lignes libres ad-hoc** en complément des actes.
- **Contexte de variables standard prédéfini** (contrat documenté) : champs patient, bloc de
  lignes à colonnes connues, totaux connus — **zéro configuration par modèle**.
- **Répétition dynamique** d'une ligne-modèle de tableau Word, mise en forme préservée,
  **sans toucher** `_replace_in_para_elem`.
- **Totaux calculés en Python** (dû / réglé / reste / nombre de lignes), formatés en style
  français.
- **Aucun paiement, aucune créance dupliquée** (conforme « source unique du dû »).
- **Aucune migration de schéma** ; lignes persistées dans `documents.variables` (JSON).

**Non-Goals:**

- Pas d'évaluateur de formules ni d'expressions configurables par modèle (abandonné par
  rapport à la conception initiale) : les colonnes et totaux sont **prédéfinis**.
- Pas de configuration de colonnes par modèle : le contrat de variables est **fixe**.
- Pas de marquage des actes comme « facturés » à la génération (la note les *référence*,
  sans modifier leur état ni leur statut de paiement) — éventuelle itération ultérieure.
- Pas de support des tableaux Word complexes (cellules fusionnées, tableaux imbriqués dans
  la ligne-modèle).
- Pas de modification du flux Mailjet ni du format de sortie (jpg/pdf).
- Pas de refonte des modèles mono-valeur existants.

## Decisions

### D1 — Contexte de variables standard prédéfini (« à la Mailjet »)

À la génération, le pont construit un **contexte** structuré, ouvert au modèle qui le
consomme par **noms de balises connus et documentés** (analogie : la *variables payload*
d'un template transactionnel Mailjet). Le contrat est **fixe** — aucune configuration de
colonnes par modèle :

- **Balises document** (remplies une fois) :
  - Patient : `<NOM>`, `<PRENOM>`, `<EMAIL>`, `<TELEPHONE>`, `<ADRESSE>`, `<DATE_NAISSANCE>`
    (déjà fournies par `_patient_replacements`).
  - Note : `<DATE>` (date d'émission, par défaut aujourd'hui).
  - Totaux : `<TOTAL_DU>`, `<TOTAL_REGLE>`, `<RESTE_A_PAYER>`, `<NB_ACTES>` (+ alias
    `<TOTAL>` = `<TOTAL_DU>` pour confort).
- **Balises de ligne** (`L_*`, répétées par ligne) : `<L_DATE>`, `<L_ACTE>`, `<L_DENTS>`,
  `<L_NOTE>`, `<L_MONTANT>`, `<L_REGLE>`, `<L_RESTE>`.

Le modèle place les `<L_*>` dans **une** ligne-modèle de tableau et les balises document
ailleurs. L'auteur du modèle choisit **lesquelles** de ces balises afficher ; le contexte
fournit **toujours** l'ensemble. Le contrat est documenté (CLAUDE.md + aide modèle).

- *Alternative écartée* : configuration de colonnes par modèle (conception initiale,
  `template_fields.scope/expression`) — éclatait la définition entre `.docx` et base, et
  imposait un évaluateur d'expressions. Le contrat fixe est plus simple et suffisant.

### D2 — Convention de balises : document vs ligne (préfixe `L_`)

Les balises de **ligne** portent le préfixe `L_` ; les balises **document** restent telles
quelles. Le nom de colonne est la balise sans préfixe, en minuscules (`L_MONTANT` →
`montant`). La regex existante `<([A-Z0-9_]+)>` matche déjà `L_*` : la distinction se fait
par **préfixe**, de façon **additive**. Un modèle contenant ≥ 1 balise `L_*` est une
**note multi-lignes** ; sinon il est « simple » (rendu inchangé).

### D3 — Répétition par clonage de la ligne `<w:tr>` (réutilise le run-splitting)

`extract_placeholders` et la génération repèrent la **ligne de tableau** (`w:tr`) contenant
≥ 1 balise `L_*` : c'est la **ligne-modèle**. À la génération, pour N lignes retenues, on
**deepcopy** le `w:tr` modèle N fois, on insère les copies en frères après le modèle, on
remplit chaque copie via la fonction **existante** `_replace_in_para_elem` (par paragraphe
de cellule) avec le dictionnaire de la ligne, puis on **retire le `w:tr` modèle** (retrait
simple si N = 0).

La duplication est **purement structurelle** (manipulation lxml) ; le remplissage des
cellules **réutilise** la logique de redistribution de runs sans la modifier. Note : comme
`_fill_docx` ne traverse pas aujourd'hui les cellules de tableau, l'expansion explore
elle-même les paragraphes de chaque cellule du `w:tr` cloné.

- *Alternatives écartées* : (a) emplacements fixes `<DATE_1..N>` (plafonné, lignes vides) ;
  (b) réécrire le tableau via OpenXML à la main (gros, fragile).

### D4 — Lignes alimentées par les actes (isolés + plans), existants ou créés à la volée

Le dialogue « Note d'honoraires » charge `repo.list_prestations` du patient (actes isolés
`plan_id IS NULL` **et** actes des plans via `repo.list_plans` + `list_prestations(plan_id=…)`),
les présente **regroupés** (Actes isolés / par plan) et **pré-cochés**. Chaque acte retenu
devient une **ligne** par projection :

| Colonne contexte | Source `Prestation` |
|---|---|
| `date`    | `date_acte` (formatée `jj/mm/aaaa`) |
| `acte`    | `libelle` |
| `dents`   | `dents` (chaîne FDI, ex. « 26, 27 ») |
| `note`    | `note` |
| `montant` | `montant` (format `format_montant`) |
| `regle`   | `montant_regle` |
| `reste`   | `reste` (propriété dérivée) |

Pour facturer un poste non encore saisi, l'utilisateur **ajoute un nouvel acte** via la
**carte d'acte réutilisée** (`_acte_card` : référentiel, libellé, montant, date, dents avec
odontogramme, note). À l'enregistrement (brouillon ou génération), ces actes sont **créés
comme actes isolés** (`repo.create_prestation`, `plan_id=NULL`) — donc **tracés dans la dette**
et **visibles dans l'onglet Actes** — puis projetés en lignes comme ci-dessus. La création est
**idempotente** (un acte déjà créé lors d'une tentative précédente est mis à jour, non
dupliqué, via `pres_id`). **Plus de « ligne libre » non tracée** (cf. *Resolved Decisions*).
L'ordre des lignes = actes cochés (ordre d'affichage) puis nouveaux actes saisis.

### D5 — Totaux calculés en Python (pas d'évaluateur de formules)

Les totaux document sont calculés directement sur les lignes retenues, sans expression
configurable :

- `<TOTAL_DU>`   = somme des `montant` de toutes les lignes.
- `<TOTAL_REGLE>`= somme des `regle` (`montant_regle` ; un acte nouvellement créé : 0).
- `<RESTE_A_PAYER>` = `TOTAL_DU − TOTAL_REGLE`.
- `<NB_ACTES>`   = nombre de lignes (entier).

Montants formatés via `format_montant` (espace milliers, virgule décimale) ; `NB_ACTES`
rendu en entier. Un `montant` manquant/non numérique d'une ligne est traité comme 0.

- *Alternative écartée* : évaluateur borné fondé sur `ast` (conception initiale,
  `src/formula.py`) — inutile dès lors que colonnes et totaux sont prédéfinis ; supprime
  une surface de risque et du code.

### D6 — Aucun paiement, pas de double-comptage (cross-ref `plans-de-traitement`)

Conformément à « source unique du dû » (`plans-de-traitement`, exigences *Source unique du
dû* et *Génération de document sans paiement*), la génération d'une note d'honoraires ne
SHALL **jamais** créer de paiement ni proposer de le faire. La note **référence** les actes ;
le dû et les règlements restent suivis **sur les actes**. `documents.montant` reçoit le
total de la note **uniquement** comme valeur d'affichage/email — **pas** comme une créance,
qui serait un double-comptage avec les actes. Aucune case « créer un paiement ».

### D7 — Persistance des lignes dans `documents.variables` (clé réservée), sans migration

`variables` reste un objet JSON. Pour une note multi-lignes, on ajoute une **clé réservée**
`__lignes__` : liste d'objets `{ source: "acte"|"libre", prestation_id?: int, date, acte,
dents, note, montant, regle }` (**données brutes** retenues ; les totaux et formats sont
**recalculés** au rendu, jamais stockés). Les balises document mono-valeur restent des clés
`TAG` comme aujourd'hui. Les documents sans `__lignes__` sont chargés/rendus comme avant.
**Aucune migration de schéma** : `documents.variables`, `documents.montant`,
`documents.acte_date` existent déjà.

### D8 — `acte_date` déterministe ; `acte` résumé (idempotence du nom de fichier)

- `document.acte_date` = **1re date** des lignes (déterministe) → nom de fichier et
  classement stables (idempotence inchangée, cf. `build_filename`).
- `document.acte` = court résumé optionnel pour l'affichage liste (ex. « Détartrage,
  Composite +2 »), non normatif.

### D9 — UI : dialogue « Note d'honoraires » enrichi (`crm/app.py`)

Le bouton dédié « Note d'honoraires » (existant, filtré par catégorie) ouvre un dialogue
qui, pour un modèle « note multi-lignes », affiche :

- la **liste des actes** du patient, **regroupée** (Actes isolés / par plan), chaque acte
  avec une **case à cocher pré-cochée** (date, libellé, montant, reste) ;
- une section **« Nouveaux actes »** : « + Ajouter un acte » empile des **cartes d'acte**
  réutilisées (`_acte_card` : référentiel, libellé, montant, date, dents avec odontogramme,
  note), créées comme **actes isolés** à l'enregistrement (suivies dans la dette) ;
- le **récapitulatif recalculé en direct** (dû / réglé / reste), via la même carte
  `_money_summary` que la fiche patient (fond blanc), placée en bas du dialogue ;
- les actions habituelles (Enregistrer en brouillon / Générer / Générer et imprimer).

Pour un modèle « simple » (sans `<L_*>`), le dialogue conserve le **formulaire mono-valeur
actuel** (`_resolve_fields`). La reprise d'un brouillon multi-lignes restitue lignes, ordre
et (dé)sélections depuis `__lignes__`.

## Risks / Trade-offs

- **Clonage `w:tr` via lxml** (insertion de frères, namespaces, `w:trPr`). → *Mitigation* :
  `deepcopy` du `w:tr` complet ; **vérifier le rendu réel** (pas seulement la chaîne),
  conformément au gotcha CLAUDE.md ; tester sur un `.docx` réel (Word requis).
- **Cellules de tableau non traversées aujourd'hui** par `_fill_docx`. → *Mitigation* :
  l'expansion traverse explicitement les paragraphes des cellules du `w:tr` cloné ; les
  balises document restent remplies par le chemin existant (hors tableau).
- **Hypothèse sur la structure du tableau** (une seule ligne-modèle, pas de cellules
  fusionnées). → *Mitigation* : détecter/valider la ligne-modèle ; message d'erreur clair si
  plusieurs lignes-modèles ou structure non supportée ; documenter la convention.
- **Double-comptage du dû** si le total était traité comme créance. → *Mitigation* : D6 —
  aucun paiement, `documents.montant` purement informatif ; le suivi reste sur les actes.
- **Compat ascendante de `variables`**. → *Mitigation* : clé réservée `__lignes__` ignorée
  par le chemin mono-valeur ; documents existants intacts ; aucune migration.
- **Formatage des montants/dates** des lignes. → *Mitigation* : réutiliser `format_montant`
  et le formatage de dates de `_format_variable`/`generator` ; `NB_ACTES` en entier.

## Migration Plan

1. **Schéma** : **aucune migration** — `documents.variables` (JSON), `documents.montant` et
   `documents.acte_date` existent déjà ; `SCHEMA_VERSION` **inchangé**.
2. **Sauvegarde** : le backup horodaté de démarrage (`backup_db`) couvre le déploiement ;
   aucune transformation de données n'est introduite.
3. **Déploiement** : nouvelle `.exe` posée à côté des données existantes ; les notes
   multi-lignes apparaissent dès qu'un modèle contient des balises `<L_*>`. Aucun document
   existant modifié.
4. **Rollback** : aucune donnée transformée ; un retour à la build précédente lit les
   anciens documents normalement (les `__lignes__` éventuels sont simplement ignorés).
5. **Validation pré-livraison** (manuelle, Word requis) : copier un `cabinet.db` de
   `backups/`, lancer la nouvelle build, vérifier qu'un patient/document/paiement existant
   se charge et se rend, puis générer une note multi-lignes depuis des actes de bout en bout.

## Resolved Decisions

- **Source des lignes** — *résolu* : **actes (isolés + plans)** existants cochés **+ nouveaux
  actes isolés** créés depuis la note (carte d'acte réutilisée). Les « lignes libres » non
  tracées sont **abandonnées** : un poste à facturer devient un acte (suivi dans la dette,
  visible dans l'onglet Actes), pour une UX plus simple et un dû cohérent (source unique).
- **Modèle de variables** — *résolu* : **contexte standard prédéfini** (contrat fixe
  documenté), pas de configuration de colonnes par modèle.
- **Évaluateur de formules** — *résolu* : **abandonné** (`src/formula.py` non créé) ; totaux
  calculés en Python.
- **Migration de schéma** — *résolu* : **aucune** ; lignes dans `documents.variables`.
- **Paiement à la génération** — *résolu* : **aucun** (« source unique du dû »).
- **Saisie d'un nouvel acte invalide** — *résolu* : carte sans libellé ignorée ; montant
  invalide bloque la génération (message clair), sans création partielle.
- **Impression / envoi** — *résolu* : une note multi-lignes s'imprime et s'envoie comme un
  document simple (fichier généré identique en nature), rien à changer.

## Open Questions

- **Réordonnancement des lignes** : ordre par défaut = actes existants cochés (isolés puis
  plans), nouveaux actes saisis en fin. Le glisser-déposer est **optionnel** dans cette
  itération ; à trancher selon le coût UI Flet (`ft.ReorderableListView`).
- **Marquage « facturé »** des actes inclus dans une note : hors périmètre ici ; à évaluer
  si le besoin de tracer « quel acte a été facturé dans quelle note » se confirme.
