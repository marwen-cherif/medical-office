## 1. Évaluateur d'expressions borné (`src/formula.py`)

- [ ] 1.1 Créer `src/formula.py` : parser `ast.parse(mode="eval")` + validation par liste blanche de nœuds (`Expression`, `BinOp` Add/Sub/Mult/Div, `UnaryOp` UAdd/USub, `Constant` numérique, `Name` Load, `Call` restreint)
- [ ] 1.2 Implémenter la portée **ligne** : `eval_line(expr, row)` — `Name` = colonne de la ligne, `Call` interdit, arithmétique seule
- [ ] 1.3 Implémenter la portée **document** : `eval_doc(expr, rows)` — fonctions `SUM/COUNT/AVG/MIN/MAX` sur une colonne + arithmétique sur agrégats/constantes
- [ ] 1.4 Gérer les erreurs explicites : fonction/opérateur/nœud non autorisé, colonne inexistante, division par zéro (aucune exécution de code arbitraire)
- [ ] 1.5 Exposer `validate_expression(expr, scope, columns)` pour la validation à la configuration (parse + essai à blanc)
- [ ] 1.6 Écrire des tests unitaires (sans Word) : cas valides, agrégats, `COUNT` entier, division par zéro, expressions rejetées

## 2. Moteur Word : répétition de ligne de tableau (`src/doc_filler.py`)

- [ ] 2.1 Ajouter la détection de la **ligne-modèle** : repérer le `w:tr` contenant ≥ 1 balise de ligne `L_*` (préfixe convenu)
- [ ] 2.2 Étendre `extract_placeholders` pour distinguer **balises de ligne** (`L_*`, → colonnes) et **balises document**, sans casser l'API existante
- [ ] 2.3 Ajouter une fonction additive `expand_table_rows(doc, line_rows)` : `deepcopy` du `w:tr` modèle par ligne saisie, insertion en frères, remplissage de chaque copie via le **réutilisé** `_replace_in_para_elem`, puis retrait du modèle (retrait simple si 0 ligne)
- [ ] 2.4 Brancher l'expansion dans `_fill_docx`/`fill_and_export_pdf` (paramètre optionnel `line_rows`), comportement **inchangé** quand aucune ligne-modèle n'est présente
- [ ] 2.5 Vérifier le **rendu réel** (pas seulement la chaîne) : mise en forme préservée (gras, bordures, alignement) sur un `.docx` de test — gate manuelle Windows + Word

## 3. Schéma & configuration template (`crm/db.py`, `crm/repo.py`)

- [ ] 3.1 Ajouter à `template_fields` les colonnes nullable `scope TEXT DEFAULT 'document'` et `expression TEXT` (expand-only)
- [ ] 3.2 Ajouter le step `_migrate()` idempotent gardé par `_column_exists`, bumper `SCHEMA_VERSION`
- [ ] 3.3 Garantir le **snapshot pré-migration** labellisé (`cabinet-pre-v<N>-…db`) **avant** la migration, exempt du prune `KEEP=10`
- [ ] 3.4 Étendre la dataclass `TemplateField` (+ `_row_to_*`, CRUD `list_template_fields`/`replace_template_fields`) avec `scope` et `expression`
- [ ] 3.5 Tester la migration sur une **copie de `cabinet.db` de production** : les lignes existantes prennent `scope='document'`, documents/patients/paiements intacts

## 4. Configuration des templates « tableau » (`crm/templates.py`)

- [ ] 4.1 Déterminer le **type de template** (simple vs tableau) à partir des balises de ligne détectées par `extract_placeholders`
- [ ] 4.2 Auto-détecter les **colonnes de ligne** (`L_*`) et proposer leur saisie (libellé, type `text|number|date`)
- [ ] 4.3 Permettre la déclaration des **champs calculés** : `computed_line` (ex. `montant = quantite * prix_unitaire`) et `computed_doc` (ex. `TOTAL = SUM(montant)`), avec désignation du champ « total »
- [ ] 4.4 Valider chaque expression à l'enregistrement via `src.formula.validate_expression` (refus + message clair si invalide)

## 5. Pont CRM : génération multi-lignes (`crm/generator.py`)

- [ ] 5.1 Sérialiser/désérialiser les lignes saisies sous la clé réservée `__lignes__` de `documents.variables` (saisies brutes uniquement)
- [ ] 5.2 Construire les remplacements de **ligne** : appliquer `computed_line` par ligne, formater dates (`jj/mm/aaaa`) et montants (`format_montant`), `COUNT` en entier
- [ ] 5.3 Calculer les **agrégats document** (`computed_doc`) via `src.formula.eval_doc` et les injecter comme balises document (`<TOTAL>`, `<NB_ACTES>`, …)
- [ ] 5.4 Reporter le **total** sur `document.montant`, fixer `document.acte_date` = 1re date des lignes, `document.acte` = résumé court optionnel
- [ ] 5.5 Passer les `line_rows` au moteur (`expand_table_rows`) dans `render_document` ; conserver le chemin mono-date inchangé quand pas de `__lignes__`
- [ ] 5.6 Adapter `save_draft`/`update_draft` pour persister les lignes et recalculer le total (brouillon sans appel Word)
- [ ] 5.7 Vérifier l'envoi Mailjet : variables d'email (total, 1re date, type) cohérentes pour un document tableau

## 6. UI : éditeur de lignes (`crm/app.py`)

- [ ] 6.1 Détecter le type « tableau » du template choisi et basculer vers l'**éditeur de lignes** (sinon, formulaire mono-valeur actuel)
- [ ] 6.2 Implémenter l'éditeur : « + Ajouter une ligne », suppression par ligne, **réordonnancement par glisser-déposer (drag)** via `ft.ReorderableListView` (poignée de drag dédiée pour ne pas gêner l'édition des champs), champs typés (datepicker pour `date`)
- [ ] 6.3 Afficher les **colonnes calculées** en lecture seule et le **total recalculé en direct** à chaque modification (sans génération)
- [ ] 6.4 Intégrer l'éditeur dans le cycle brouillon → génération → envoi (et la reprise d'un brouillon tableau restitue lignes/ordre/valeurs)
- [ ] 6.5 Ajouter l'écran de configuration des colonnes/champs calculés dans le paramétrage des variables du template

## 7. Validation de bout en bout (Windows + Word requis)

- [ ] 7.1 Créer un template `.docx` « tableau » de test (ligne-modèle `<L_DATE> | <L_ACTE> | <L_MONTANT>`, `<TOTAL>`, `<NB_ACTES>`)
- [ ] 7.2 Générer une note regroupant 4 visites (01/05, 02/05, 05/05, 01/06) : vérifier lignes, mise en forme, `TOTAL = 390,000`, `NB_ACTES = 4`
- [ ] 7.3 Vérifier le **report paiements** : le document apparaît dans les impayés du patient avec le bon montant
- [ ] 7.4 Vérifier la **non-régression** mono-date : un template simple existant se génère/s'envoie/s'imprime comme avant
- [ ] 7.5 Vérifier les cas limites : 0 ligne, montant manquant (traité 0 dans `SUM`), expression invalide refusée à la config
- [ ] 7.6 Mettre à jour la documentation (CLAUDE.md / convention de balises `L_*` + type de template tableau)
