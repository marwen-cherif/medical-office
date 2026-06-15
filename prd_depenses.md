# PRD — Suivi des dépenses & Prestataires

> Cabinet Dr Aslem Gouiaa — CRM (Flet + SQLite). Document de référence pour
> l'implémentation. Aucun code n'est inclus ici ; le PRD décrit le quoi et le comment
> au niveau conception. Lire impérativement la section **9** (préservation des données)
> avant toute évolution de schéma.

## 0. Décisions validées

1. **Stockage des factures** : on **généralise la table `documents`** existante (ajout
   `prestataire_id` nullable + `patient_id` rendu nullable) plutôt qu'une table séparée,
   afin de réutiliser à 100 % les jobs et le suivi avec un simple filtre patient/prestataire.
2. **Envoi** : les factures prestataires sont **générées / archivées seulement** (pas
   d'envoi email Mailjet). Le suivi Mailjet reste réservé aux notes patients.
3. **Navigation** : **Prestataires** devient une entrée du rail (comme Patients) ;
   **Dépenses** devient un sous-onglet d'une page **Finances** (ex-« Paiements »), au même
   titre que l'onglet Paiements — sur le modèle des sous-onglets de la page Travaux.

---

## 1. Objectif & problème

Le cabinet sait suivre ses **entrées d'argent** (paiements patients) mais n'a aucun moyen de
suivre ses **sorties d'argent** (dépenses : fournisseurs, laboratoires, loyers…).

Objectif : offrir un suivi des **sorties** symétrique aux paiements :
- gérer des **prestataires** (annuaire) ;
- générer leurs **factures** depuis des modèles Word (mécanisme identique aux notes
  d'honoraires) ;
- suivre chaque **dépense** (montant, échéance, statut réglé / en attente, date et mode de
  règlement) ;
- intégrer ces données au **tableau de bord** (KPI + **balance entrées / sorties**).

---

## 2. Périmètre

**Inclus**
- Entité **Prestataire** (nom, prénom, adresse, email, téléphone) + page liste/fiche + CRUD.
- Génération de **factures prestataires** via modèles Word (mécanisme identique aux notes).
- **Modèles typés** patient / prestataire (paramétrage).
- Entité **Dépense** (montant, échéance optionnelle, statut, date/mode de règlement),
  créable depuis le brouillon de facture (case à cocher) et listée/filtrée.
- Suppression d'une ligne de dépense ; **règlement** d'une dépense (modale type paiement).
- **Jobs** de génération étendus aux factures prestataires (+ filtre patient/prestataire).
- **Tableau de bord** : KPI dépenses + **graphe balance entrées / sorties**.
- **Pagination partout** (listes prestataires, dépenses, documents, jobs).

**Hors périmètre**
- Envoi email des factures prestataires (génération/archivage seulement).
- Comptabilité avancée (TVA, écritures, exports comptables).
- Catégorisation analytique des dépenses (évolution future possible).

---

## 3. Modèle de données (SQLite — `crm/db.py`)

Toutes les évolutions sont **additives / expand-only** sauf la généralisation de `documents`
qui exige une **reconstruction** encadrée (voir §9). Bump `SCHEMA_VERSION` de **5 → 6**.

### 3.1 Nouvelle table `prestataires` (calquée sur `patients`)
```sql
CREATE TABLE IF NOT EXISTS prestataires (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    nom          TEXT NOT NULL,
    prenom       TEXT NOT NULL DEFAULT '',
    slug_nom     TEXT NOT NULL,
    slug_prenom  TEXT NOT NULL,
    email        TEXT,
    telephone    TEXT,
    adresse      TEXT,
    notes        TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_prestataires_slug ON prestataires(slug_nom, slug_prenom);
```
> `prenom` n'est pas obligatoire côté UI (un prestataire peut être une raison sociale) mais
> conservé en base pour réutiliser tel quel la détection de doublons par slug
> (`find_matches`).

### 3.2 Nouvelle table `depenses` (calquée sur `paiements`)
```sql
CREATE TABLE IF NOT EXISTS depenses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    prestataire_id  INTEGER NOT NULL REFERENCES prestataires(id) ON DELETE CASCADE,
    document_id     INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    montant         REAL NOT NULL DEFAULT 0,
    statut          TEXT NOT NULL DEFAULT 'en_attente',  -- 'en_attente' | 'regle'
    mode            TEXT,
    date_echeance   TEXT,        -- optionnelle
    date_paiement   TEXT,        -- date de règlement effectif
    libelle         TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_depenses_prestataire ON depenses(prestataire_id);
```
Statuts : `en_attente` (défaut) / `regle`. Symétrie volontaire avec `paiements`
(`en_attente` / `encaisse`).

### 3.3 Typage des modèles : `template_meta`
Les modèles sont des fichiers `.docx` (aucune ligne en base aujourd'hui). On ajoute une
table légère pour leur **type** :
```sql
CREATE TABLE IF NOT EXISTS template_meta (
    template_name TEXT PRIMARY KEY,
    kind          TEXT NOT NULL DEFAULT 'patient'  -- 'patient' | 'prestataire'
);
```
Absence de ligne ⇒ `kind = 'patient'` (rétro-compatibilité : tous les modèles existants
restent des modèles patient). Helpers : `get_template_kind(name) -> str`,
`set_template_kind(name, kind)`.

### 3.4 Généralisation de `documents` (partie patient **ou** prestataire)
- Ajouter `prestataire_id INTEGER NULL REFERENCES prestataires(id) ON DELETE CASCADE`.
- Rendre `patient_id` **nullable** (aujourd'hui `NOT NULL`).
- Invariant applicatif : exactement un de `patient_id` / `prestataire_id` est renseigné
  (optionnellement matérialisé par un `CHECK` lors de la reconstruction).

SQLite ne sait pas relâcher un `NOT NULL` par `ALTER` ; cette évolution passe donc par une
**reconstruction de table** encadrée — détaillée en §9. Les colonnes ajoutées en v2–v5
(`variables`, `mailjet_opened_at`, `mailjet_clicked_at`) doivent être reportées à
l'identique dans le schéma de la table reconstruite.

---

## 4. Couche `crm/repo.py`

Reproduire les patrons existants (mêmes signatures, mêmes filtres, même pagination
`limit`/`offset`).

- **Prestataire** : dataclass `Prestataire` ; `create_prestataire`, `update_prestataire`,
  `get_prestataire`, `list_prestataires(search, limit, offset)`, `count_prestataires(search)`,
  `find_prestataire_matches(nom, prenom)`, `get_or_create_prestataire(...)` — copies directes
  de leurs équivalents patients (`crm/repo.py:146-282`), avec réutilisation de `slugify`.
- **Dépense** : dataclass `Depense` ; `create_depense` (validation `montant > 0`),
  `mark_depense_reglee(id, when, mode)` (calque `mark_paiement_encaisse`, `crm/repo.py:720`),
  `list_depenses(prestataire_id, limit, offset)`, `count_depenses_for_prestataire`,
  `delete_depense`, `list_depenses_filtered(search, statut, limit, offset, date_from, date_to)`,
  `count_depenses(...)`, `total_depenses(...)` — calques de `list_paiements_filtered` /
  `count_paiements` / `total_paiements` (`crm/repo.py:806-869`).
- **Documents** : ajouter un paramètre `partie` (`'patient' | 'prestataire' | 'tous'`) à
  `list_documents_filtered` / `count_documents_filtered` / `list_document_ids_filtered`
  (`crm/repo.py:618-665`) ; `list_documents` accepte `prestataire_id`. Inclure
  `prestataire_id` dans la dataclass `Document` et les CRUD.

---

## 5. Couche génération `crm/generator.py`

Abstraire la notion de « partie » (patient ou prestataire) qui fournit les balises auto :
- Renommer conceptuellement `AUTO_PATIENT_TAGS` en **`AUTO_PARTY_TAGS`** (mêmes tags :
  `NOM, PRENOM, EMAIL, TELEPHONE, ADRESSE, DATE_NAISSANCE` — `DATE_NAISSANCE` reste vide pour
  un prestataire). `crm/generator.py:74`.
- Généraliser `_patient_replacements` → `_party_replacements(party)` (mêmes champs ;
  fonctionne sur `Patient` comme sur `Prestataire` car attributs identiques).
- `save_draft`, `render_document`, `update_draft` acceptent une **partie** + un `party_type`,
  et enregistrent `patient_id` **ou** `prestataire_id` dans `documents`. Pas d'appel
  `send_document` pour les prestataires (génération seule).
- `build_filename` / arborescence de sortie : prévoir un sous-dossier prestataire
  (`output/prestataires/<slug>/…`) pour éviter toute collision avec les patients.

---

## 6. UI/UX (`crm/app.py`) — harmonie globale

### 6.1 Navigation (rail)
Passer de 5 à 6 entrées :
`Tableau · Patients · Prestataires · Finances · Travaux · Paramétrage`
(`_build_shell`, `crm/app.py:365-403`). Icône suggérée Prestataires :
`STOREFRONT` / `LOCAL_SHIPPING`. « Paiements » est renommée **Finances** et reçoit un
**sous-menu** Paiements / Dépenses sur le modèle de `_travaux_submenu`
(`crm/app.py:2011-2028`) ou `_param_submenu` (`crm/app.py:1737-1754`).

### 6.2 Page Prestataires
Calque de `show_patients` (`crm/app.py:964-978`) : titre + bouton « Nouveau prestataire »,
champ de recherche, liste paginée, pager. Dialog création/édition calqué sur `_patient_dialog`
(`crm/app.py:2293`) avec champs **nom, prénom, adresse (TextField multiline), email,
téléphone** + détection de doublons (`find_prestataire_matches`). Fiche prestataire (calque
`show_patient_detail`, `crm/app.py:1329`) listant ses factures et ses dépenses, avec bouton
**« Nouvelle facture »**.

### 6.3 Génération de facture + lignes de dépenses
Calque de `_generate_dialog` (`crm/app.py:2374-2512`) pour les prestataires :
- Dropdown des modèles **filtré sur `kind = 'prestataire'`**.
- Saisie des variables du modèle (réutilise `_resolve_fields` / `build_fields`).
- À la place de la case « Créer un paiement en attente », une case **« Ajouter une ligne de
  dépense »** (cochée par défaut) + montant **+ échéance optionnelle** (`_date_field`,
  `crm/app.py:698`). À l'enregistrement du brouillon, si cochée et montant > 0 →
  `create_depense(...)` liée au document (`document_id`).
- Le format (jpg/pdf) et le mécanisme brouillon → génération restent identiques.

### 6.4 Page Finances → onglet Dépenses
Calque de `show_paiements` / `_refresh_paiements` (`crm/app.py:1609-1698`) :
- Filtres : recherche prestataire, statut (`en_attente` / `regle` / `tous`), période
  (date_from/date_to via `_date_field`).
- Carte récapitulative (total selon statut, calque `paie_summary`).
- Lignes : montant, prestataire, échéance / date de règlement, **chip** statut
  (« Réglé » vert / « En attente » navy), pagination `_pagination` (`crm/app.py:633`).
- Actions par ligne : **« Régler »** (icône `CHECK_CIRCLE`) et **« Supprimer »** (icône
  `DELETE` / `CANCEL`), + « Ouvrir la fiche » prestataire.

### 6.5 Régler / Supprimer une dépense
- **Régler** : modale calquée sur `_encaisser` (`crm/app.py:2702-2746`) — choix du **mode**
  (`_MODE_LABELS`), `mark_depense_reglee` (statut `regle`, `date_paiement`, `mode`),
  `log_audit('depense_reglee', …)`.
- **Supprimer** : modale de confirmation calquée sur `_annuler_paiement`
  (`crm/app.py:2748-2774`) → `delete_depense` + `log_audit('depense_supprimee', …)`.
- Brancher la pagination/recherche/raccourcis : étendre `_page_step`, `_reset_and`,
  `_focus_search`, `_new_for_current_view` (`crm/app.py:543-626`) aux vues `prestataires`
  et `depenses`.

### 6.6 Paramétrage — modèles typés
Sous-onglet « Modèles de documents » (`crm/app.py:1756-1768`) : afficher/saisir le **type**
(patient / prestataire) de chaque modèle. `_new_template_dialog` (`crm/app.py:2551`) reçoit
un sélecteur de type, persisté via `set_template_kind`. La liste des modèles affiche un badge
du type ; possibilité de filtrer par type.

### 6.7 Travaux — filtre patient / prestataire
Page Travaux (`show_travaux`, `crm/app.py:1973`), sous-onglets Documents et Travaux : ajouter
un filtre **partie** (Tous / Patients / Prestataires) passé à `list_documents_filtered` /
jobs. Les **jobs de génération** traitent les deux types ; les **jobs d'envoi** restent
réservés aux documents patients (les factures prestataires n'ont pas d'envoi). Le détail de
job affiche le nom de la partie indifféremment.

### 6.8 Tableau de bord — dépenses & balance
Étendre `_refresh_dashboard` (`crm/app.py:889-961`) :
- Nouveaux KPI : **Dépenses réglées**, **Dépenses en attente** (échéances non réglées),
  **Solde net** (encaissé − réglé) — via `repo.total_depenses(...)`.
- **Graphe balance entrées / sorties** : nouveau graphe canvas (deux barres / donut
  comparatif), construit comme `_camembert` (`crm/app.py:845-887`) avec `flet.canvas` —
  **aucune dépendance ajoutée** (Flet + PyMuPDF uniquement). Légende Entrées (vert) /
  Sorties (rouge/ambre) + solde.

---

## 7. Patterns réutilisés (rester homogène)
- Pagination : `_pagination`, `_clamp_page`, `PAGE_SIZE` (`crm/app.py:628-655`).
- Dates : `_date_field`, `_iso_to_fr`, `_fr_to_iso`, `_date_iso` (`crm/app.py:698`).
- Boutons / busy / toasts / dialogues : `_btn`, `_run_busy`, `_toast`, `_show_dialog`.
- Palette & libellés de statut (en haut de `crm/app.py`) — ajouter les libellés Dépense.
- Audit : `repo.log_audit` pour chaque création / règlement / suppression de dépense.

---

## 8. Statuts & libellés

| Domaine | Valeurs | Libellés UI |
|---|---|---|
| Dépense `statut` | `en_attente`, `regle` | « En attente », « Réglé » |
| Modèle `kind` | `patient`, `prestataire` | « Patient », « Prestataire » |
| Document `partie` (dérivé) | `patient_id` / `prestataire_id` | « Patient » / « Prestataire » |

---

## 9. Préservation des données & migration (CRITIQUE — lire `CLAUDE.md`)

1. **Bump `SCHEMA_VERSION` 5 → 6** + étape idempotente dans `_migrate()`
   (`crm/db.py:164-253`).
2. **Tables additives** (`prestataires`, `depenses`, `template_meta`) : ajoutées au schéma
   statique via `CREATE TABLE IF NOT EXISTS` — sans risque.
3. **Reconstruction de `documents`** (relâcher `patient_id NOT NULL` + ajouter
   `prestataire_id`) : **seule opération réellement sensible du projet**.
   - **Le filet de sécurité existe déjà** : `connect()` (`crm/db.py:215-219`) appelle
     `_snapshot_before_migration()` (`crm/db.py:186-202`) **avant** `_migrate()`. Une copie
     octet pour octet du `.db` est écrite dans `backups/pre-migration/cabinet-v5-to-v6-<stamp>.db`,
     **exemptée de la purge `KEEP=10`** (`_prune` ne balaie que `backups/cabinet-*.db`).
     ⇒ l'état d'origine est toujours restaurable, même en cas de crash en pleine migration.
     *(Le `CLAUDE.md` règle 3 est périmé sur ce point : le snapshot ne tourne pas « après
     `connect()` », il tourne bien avant la migration.)*
   - Migration encadrée et **idempotente**, gardée par une **sentinelle `meta`**
     (`docs_party_v6`), **dans une seule transaction** (rollback atomique) :
     `PRAGMA foreign_keys=OFF` → créer `documents_new` (schéma cible : `patient_id` nullable,
     `prestataire_id` nullable, **toutes** les colonnes v1–v5 reportées à l'identique) →
     `INSERT INTO documents_new (col1, …, coln) SELECT col1, …, coln FROM documents`
     (**liste de colonnes explicite**, `id` copié tel quel pour préserver les références) →
     `DROP TABLE documents` → `ALTER TABLE documents_new RENAME TO documents` → recréer
     `idx_documents_patient` (+ futur `idx_documents_prestataire`) → `PRAGMA foreign_keys=ON`.
   - **Vérification anti-perte** : comparer `COUNT(*)` avant/après dans la transaction ; si
     différent ⇒ `ROLLBACK` et abort (l'app refuse de démarrer plutôt que de dégrader).
   - **Préservation des liens** : `paiements.document_id` continue de pointer car les `id`
     de `documents` sont copiés à l'identique (ne jamais laisser `AUTOINCREMENT` réattribuer).
   - Guard `_column_exists(conn, 'documents', 'prestataire_id')` + sentinelle pour éviter
     toute reprise sur une base déjà migrée.

   > **Alternative à risque zéro** (si la sécurité prime sur l'harmonie du code) : une table
   > **`factures` séparée** pour les prestataires ne touche pas à `documents` — aucune
   > reconstruction, aucun risque sur l'existant. Coût : duplication d'une partie de la
   > logique de génération/jobs. À arbitrer avant le Lot 1.
4. **Anti-downgrade** : `connect()` refuse déjà une base plus récente (`SchemaTooNewError`)
   — inchangé.
5. **Aucune opération destructive** hors `crm.reset`.
6. **Idempotence par nom de fichier** : la sortie prestataire va dans un sous-dossier dédié
   pour ne pas collisionner avec les notes patients (cf. règle 6).
7. **Test sur base réelle** (Windows + Word) : copier un `cabinet.db` de prod depuis
   `backups/`, lancer le build, vérifier que patients/documents/paiements existants se
   chargent et se rendent **après** reconstruction de `documents`.

---

## 10. Plan de livraison (lots)

- **Lot 1 — Données** : `prestataires`, `depenses`, `template_meta`, migration v6 + snapshot
  pré-migration ; CRUD repo + tests manuels sur base de prod.
- **Lot 2 — Prestataires & factures** : page Prestataires, fiche, génération de facture
  (modèles typés), lignes de dépenses à la création du brouillon.
- **Lot 3 — Finances / Dépenses** : page Finances (onglets Paiements/Dépenses), liste filtrée,
  régler/supprimer, pagination ; Travaux : filtre patient/prestataire.
- **Lot 4 — Tableau de bord** : KPI dépenses + graphe balance entrées/sorties.

---

## 11. Vérification (manuelle, Windows + Word requis)

1. `python crm_app.py` sur une **copie d'un `cabinet.db` de prod** : vérifier migration v6,
   snapshot `cabinet-pre-v6-*.db` créé, patients/documents/paiements intacts.
2. Créer un prestataire, détecter un doublon, éditer.
3. Créer un modèle typé « prestataire » ; générer une facture ; cocher « ligne de dépense »
   avec échéance → vérifier la dépense liée au document.
4. Page Finances : filtrer dépenses par statut/période ; régler (mode) ; supprimer ;
   pagination > 1 page.
5. Travaux : filtre Patients/Prestataires ; job de génération sur factures prestataires.
6. Tableau de bord : KPI dépenses corrects + graphe balance entrées/sorties cohérent.

---

## 12. Fichiers concernés (implémentation ultérieure)

- `crm/db.py` — schéma + migration v6 (reconstruction `documents`, snapshot pré-migration).
- `crm/repo.py` — dataclasses + CRUD Prestataire / Depense ; filtre `partie` documents.
- `crm/generator.py` — abstraction « partie », génération facture prestataire (sans envoi).
- `crm/templates.py` — typage des modèles (`template_meta`).
- `crm/app.py` — rail, page Prestataires, fiche, dialog facture+dépenses, page Finances
  (onglets), modales régler/supprimer, paramétrage typé, filtre Travaux, dashboard.
- `crm/backup.py` — snapshot pré-migration labellisé exempté de l'élagage.
