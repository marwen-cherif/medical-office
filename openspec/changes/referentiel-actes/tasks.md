## 1. Schéma & migration (crm/db.py)

- [x] 1.1 Ajouter à `_SCHEMA` la table `CREATE TABLE IF NOT EXISTS actes (id INTEGER PRIMARY KEY AUTOINCREMENT, libelle TEXT NOT NULL, slug_libelle TEXT NOT NULL, prix REAL NOT NULL DEFAULT 0, code TEXT, actif INTEGER NOT NULL DEFAULT 1, sort_order INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT (datetime('now')))` + index sur `slug_libelle` et sur `actif`.
- [x] 1.2 Bumper `SCHEMA_VERSION` de 8 à 9. Aucune étape `_migrate()` de transformation requise (table neuve créée par `_SCHEMA`) ; vérifier que `connect()` déclenche bien le snapshot pré-migration sur une base v8.
- [x] 1.3 Confirmer le respect des règles de préservation (additif, non destructif, anti-downgrade déjà en place).

## 2. Couche d'accès aux données (crm/repo.py)

- [x] 2.1 Ajouter la dataclass `Acte(id, libelle, prix, code, actif, sort_order)` et `_row_to_acte`.
- [x] 2.2 `create_acte(conn, acte)` : valide libellé non vide et prix ≥ 0 (lève `ValueError` sinon), calcule `slug_libelle` via `slugify`, insère, renvoie l'acte avec son id.
- [x] 2.3 `update_acte(conn, acte)` : met à jour libellé/slug/prix/code/ordre.
- [x] 2.4 `set_acte_actif(conn, acte_id, actif)` : active/désactive (retrait non destructif) ; `delete_acte(conn, acte_id)` réservé à un acte jamais utilisé.
- [x] 2.5 `get_acte(conn, acte_id)` (lookup pour le contrat de pré-remplissage).
- [x] 2.6 `_acte_filter_clause(search, actifs_seulement)` + `list_actes(conn, search="", actifs_seulement=True, limit=None, offset=0)` et `count_actes(conn, search="", actifs_seulement=True)` : recherche insensible aux accents sur `slug_libelle` (patron `LIKE` des patients/documents), tri `sort_order, slug_libelle`, pagination `LIMIT/OFFSET`.
- [x] 2.7 Détection d'homonyme (avertissement non bloquant) : helper renvoyant un acte actif au libellé identique s'il existe.

## 3. Interface — Paramétrage › Actes (crm/app.py)

- [x] 3.1 Ajouter l'onglet « Actes » au sous-menu de Paramétrage (`_param_submenu`) à côté de Modèles / Modèles d'email / Imprimante.
- [x] 3.2 `show_actes()` + `_refresh_actes()` calqués sur `show_mail_templates` / `_refresh_mail_templates` : champ de recherche (`_search_field`), liste paginée (`_pagination`, `PAGE_SIZE`), bascule « inclure les inactifs ». _(L'accès se fait par `show_parametrage("actes")` via le sous-menu, comme les autres onglets ; pas de `show_actes()` séparé.)_
- [x] 3.3 `_acte_row(acte)` : libellé, prix formaté (`_fmt_prix`, 2 décimales — cohérent avec l'affichage CRM des montants ; cf. note ci-dessous), badge « inactif » le cas échéant, actions (éditer, désactiver/réactiver).
- [x] 3.4 `_acte_dialog(acte=None)` (`_show_dialog`) : champs libellé (requis) + prix (numérique) + code (optionnel) ; validation montant ≥ 0 ; avertissement non bloquant si libellé déjà présent ; entrée d'audit (`log_audit`).
- [x] 3.5 Ergonomie clavier cohérente (Ctrl+N nouvel acte, Ctrl+S/Ctrl+Entrée enregistrer, sélection auto des champs) comme les autres dialogues.

> Note d'implémentation (écart vs design D3) : le design prévoyait `format_montant`,
> mais celui-ci formate à **3 décimales** (dinar, pour les modèles Word) alors que le
> scénario de la spec exige « 1 800,00 » (2 décimales) et que l'UI CRM affiche tous les
> montants à 2 décimales. Un helper local `_fmt_prix` (espace milliers, virgule, 2 déc.)
> a donc été ajouté plutôt que de modifier `src/`. **Retrait = désactivation non
> destructive uniquement** (icône œil), réversible : aucune suppression dure n'est
> exposée dans l'UI (décision produit — éviter le doublon de mécanismes et rester
> cohérent avec la philosophie de préservation des données du projet). `repo.delete_acte`
> reste dans le code pour le `reset` et une éventuelle future purge **gardée** (actes
> jamais référencés), comme prévu par la spec.

## 4. Vérification (manuelle)

> Vérifications automatiques déjà passées (hors GUI/Word) : `python -m py_compile`
> sur `db.py`/`repo.py`/`app.py` ✓ ; constantes d'icônes Flet valides ✓ ; test
> headless db+repo sur base temporaire ✓ (création + validations libellé vide /
> prix < 0, tri, recherche insensible aux accents, pagination, doublon
> insensible casse/accents, désactivation/réactivation avec exclusion par défaut,
> update prix, get_acte, delete, et `_fmt_prix(1800) == "1 800,00"`).
> Restent ci-dessous les vérifications qui exigent un clic dans l'UI et/ou Word.

- [ ] 4.1 Créer plusieurs actes, vérifier le tri, la recherche insensible aux accents et la pagination au-delà d'une page. _(Logique repo vérifiée ; reste le click-through UI.)_
- [ ] 4.2 Éditer un prix et vérifier l'affichage formaté ; vérifier le refus d'un libellé vide et l'avertissement de doublon. _(Logique repo + `_fmt_prix` vérifiées ; reste l'affichage et le double-clic de confirmation dans le dialogue.)_
- [ ] 4.3 Désactiver puis réactiver un acte ; vérifier qu'un acte inactif est exclu de la liste de saisie par défaut et visible via « inclure les inactifs ». _(Logique repo vérifiée ; reste la bascule UI.)_
- [ ] 4.4 Lancer la nouvelle build sur une **copie d'une base `cabinet.db` de production** : vérifier le chargement intact des patients/documents/paiements, la création de la table `actes` (vide) et la présence du snapshot pré-migration.
