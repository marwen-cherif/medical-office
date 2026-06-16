# PRD — Suivi des dépenses & Prestataires

> Cabinet Dr Aslem Gouiaa — CRM (Flet + SQLite). Document de référence pour
> l'implémentation. Aucun code n'est inclus ici ; le PRD décrit le quoi et le comment
> au niveau conception. Lire impérativement la section **9** (préservation des données)
> avant toute évolution de schéma.

## 0. Décisions validées

1. **Pas de génération de facture fournisseur dans le CRM.** Les factures fournisseurs sont
   **importées** (upload d'un PDF/image existant), jamais rendues depuis un modèle Word. Les
   **modèles Word restent exclusivement réservés aux documents patients** (notes d'honoraires).
2. **Stockage des factures importées** : une **table `factures` séparée**, dédiée aux
   prestataires. La table `documents` (notes patients) **n'est pas touchée** — aucune
   reconstruction, migration **purement additive** et sans risque sur l'existant. Comme les
   factures n'ont **ni génération Word ni jobs/envoi** à mutualiser avec les notes patients,
   il n'y a aucun intérêt à généraliser `documents`. Voir §3.3.
3. **Envoi** : les factures prestataires sont **archivées seulement** (pas d'envoi email
   Mailjet). Le suivi Mailjet reste réservé aux notes patients.
4. **Navigation** : **Prestataires** devient une entrée du rail (comme Patients) ;
   **Dépenses** devient un sous-onglet d'une page **Finances** (ex-« Paiements »), au même
   titre que l'onglet Paiements — sur le modèle des sous-onglets de la page Travaux.
5. **Extraction IA du montant** : à l'import, le CRM **extrait automatiquement le montant** de
   la facture (IA/OCR). Désactivable par une case à cocher (activée par défaut) ; montant
   **toujours éditable** manuellement.
6. **Règlements partiels** : une dépense porte un **montant total dû** et un **cumul réglé** ;
   le **reste à payer** est dérivé. Trois statuts : `en_attente` / `regle_partiellement` /
   `regle`. Un règlement initial (avance) est saisi à l'upload en **% ou montant** + **motif**.

---

## 1. Objectif & problème

Le cabinet sait suivre ses **entrées d'argent** (paiements patients) mais n'a aucun moyen de
suivre ses **sorties d'argent** (dépenses : fournisseurs, laboratoires, loyers…).

Objectif : offrir un suivi des **sorties** symétrique aux paiements :
- gérer des **prestataires** (annuaire) ;
- **importer et archiver** leurs **factures** (upload PDF/image, pas de génération) ;
- suivre chaque **dépense** (montant, échéance, statut réglé / en attente / **réglé
  partiellement**, **règlements successifs** et reste à payer) ;
- intégrer ces données au **tableau de bord** (KPI + **balance entrées / sorties**).

### 1.1 Parcours utilisateur cible — dépense fournisseur

Flux complet d'une dépense fournisseur, de la création à son extinction :

1. **Profil fournisseur** — création de la fiche prestataire/fournisseur dans le CRM (§6.2).
2. **Import & lecture de la facture** — upload du document (PDF/image). Le CRM **extrait
   automatiquement le montant via IA/OCR**, extraction **désactivable** par une case à cocher
   (activée par défaut selon sa fiabilité). Le montant extrait pré-remplit le champ et reste
   éditable (§6.3).
3. **Règlement initial** — à l'upload, indication de la **part déjà payée** au fournisseur
   (en **% ou en montant exact**) + un champ **motif** (ex. « Avance »).
4. **Traçabilité & fiche** — la facture est **horodatée** et **archivée dans le répertoire du
   fournisseur** (`output/prestataires/<slug>/…`). Une **ligne de dépense** est ajoutée
   automatiquement à sa fiche avec le statut adéquat : **« À régler »** (rien payé) ou
   **« Réglé partiellement »** (avance saisie).
5. **Suivi & solde** — lors d'un paiement ultérieur, **un clic sur la ligne de dépense**
   ouvre la saisie du **nouveau montant versé** ; le CRM **recalcule et met à jour
   automatiquement le reste à payer** (et le statut quand le solde atteint zéro → « Réglé »).
6. **Suivi financier (Dashboard)** — le tableau de bord centralise les données pour afficher
   la **balance** entre les **attentes de paiement** (encaissements clients) et les **dettes**
   (factures fournisseurs à régler) (§6.8).

> **Point de conception — extraction IA (étape 2).** L'extraction du montant peut nécessiter
> un **service externe payant** (vision/OCR) : un appel réseau et potentiellement une nouvelle
> dépendance, à arbitrer (cf. la contrainte « aucune dépendance ajoutée » du dashboard, §6.8).
> Toujours **éditable manuellement** par l'utilisateur et **désactivable** (case à cocher) ;
> en cas d'échec ou d'extraction désactivée, saisie manuelle du montant. À cadrer avant le
> Lot 2.

---

## 2. Périmètre

**Inclus**
- Entité **Prestataire** (nom, prénom, adresse, email, téléphone) + page liste/fiche + CRUD.
- **Import de facture fournisseur** (upload PDF/image) avec **extraction IA du montant**
  (case à cocher, activée par défaut ; montant toujours éditable manuellement) et archivage
  horodaté dans le répertoire du prestataire.
- Entité **Dépense** avec **règlement partiel** (montant total dû, cumul réglé, reste à payer
  dérivé, échéance optionnelle, statut, date/mode/motif de règlement), créée à l'import de la
  facture (case à cocher) et listée/filtrée.
- **Règlement initial** à l'upload : part déjà payée en **% ou montant** + **motif** (avance).
- **Règlements successifs** : clic sur une ligne → saisie d'un nouveau versement, reste à
  payer recalculé ; suppression d'une ligne de dépense.
- **Tableau de bord** : KPI dépenses + **graphe balance entrées / sorties**.
- **Pagination partout** (listes prestataires, dépenses, documents).

**Hors périmètre**
- **Génération de factures prestataires** depuis des modèles Word (les modèles restent
  réservés aux documents patients).
- Envoi email des factures prestataires (archivage seulement).
- Comptabilité avancée (TVA, écritures, exports comptables).
- Catégorisation analytique des dépenses (évolution future possible).
- Extraction IA d'autres champs que le montant (date, n° de facture…) — évolution future.

---

## 3. Modèle de données (SQLite — `crm/db.py`)

Toutes les évolutions sont **purement additives / expand-only** : nouvelles tables via
`CREATE TABLE IF NOT EXISTS`, **aucune reconstruction** ni `ALTER` destructeur. `documents`
reste **inchangée**. Bump `SCHEMA_VERSION` de **5 → 6**.

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

### 3.2 Nouvelle table `depenses` (calquée sur `paiements`, étendue au règlement partiel)
```sql
CREATE TABLE IF NOT EXISTS depenses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    prestataire_id  INTEGER NOT NULL REFERENCES prestataires(id) ON DELETE CASCADE,
    facture_id      INTEGER REFERENCES factures(id) ON DELETE SET NULL,
    montant         REAL NOT NULL DEFAULT 0,             -- montant total dû (facture)
    montant_regle   REAL NOT NULL DEFAULT 0,             -- cumul déjà versé (avance + paiements)
    statut          TEXT NOT NULL DEFAULT 'en_attente',  -- 'en_attente' | 'regle_partiellement' | 'regle'
    mode            TEXT,                                -- mode du dernier règlement
    motif           TEXT,                                -- motif du règlement initial (ex. « Avance »)
    date_echeance   TEXT,        -- optionnelle
    date_paiement   TEXT,        -- date du dernier règlement effectif
    libelle         TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_depenses_prestataire ON depenses(prestataire_id);
```
- **Reste à payer** = `montant − montant_regle` (**dérivé, non stocké**).
- **Statut dérivé du cumul** (à maintenir à chaque règlement) : `montant_regle = 0` →
  `en_attente` ; `0 < montant_regle < montant` → `regle_partiellement` ;
  `montant_regle ≥ montant` → `regle`. Symétrie volontaire avec `paiements`
  (`en_attente` / `encaisse`), enrichie d'un état partiel.
- **Historique des versements (option recommandée)** : pour tracer chaque versement (étape 5)
  plutôt que de seulement incrémenter `montant_regle`, prévoir une table fille légère
  `depense_reglements(id, depense_id REFERENCES depenses(id) ON DELETE CASCADE, montant,
  mode, motif, date_reglement, created_at)`. `depenses.montant_regle` reste le **cumul**
  (source de vérité du solde). À arbitrer au Lot 3 ; sinon, mono-champ cumulé suffisant pour
  le MVP.

### 3.3 Nouvelle table `factures` (dédiée aux prestataires)
Les factures fournisseurs **importées** vivent dans leur propre table — **`documents` n'est
pas touchée**.
```sql
CREATE TABLE IF NOT EXISTS factures (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    prestataire_id  INTEGER NOT NULL REFERENCES prestataires(id) ON DELETE CASCADE,
    fichier         TEXT NOT NULL,                       -- chemin relatif du fichier archivé
    nom_original    TEXT,                                -- nom du fichier uploadé (affichage)
    montant         REAL,                                -- montant extrait/saisi (info facture)
    libelle         TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_factures_prestataire ON factures(prestataire_id);
```
- `fichier` pointe vers le PDF/image archivé sous `output/prestataires/<slug>/…` (horodaté).
- Une facture porte **0 ou 1 dépense** (`depenses.facture_id`). `montant` ici est l'info
  « facture » ; le **suivi financier** (dû / réglé / reste) vit dans `depenses` (§3.2).
- Aucune colonne Mailjet : les factures ne sont **ni envoyées ni rendues par Word**.

> **Modèles non typés.** Aucune table `template_meta` : les modèles `.docx` restent tous des
> **modèles patient**. `crm/templates.py` est inchangé. La table `documents` reste
> **strictement patient** (notes d'honoraires) — aucune colonne ajoutée.

---

## 4. Couche `crm/repo.py`

Reproduire les patrons existants (mêmes signatures, mêmes filtres, même pagination
`limit`/`offset`).

- **Prestataire** : dataclass `Prestataire` ; `create_prestataire`, `update_prestataire`,
  `get_prestataire`, `list_prestataires(search, limit, offset)`, `count_prestataires(search)`,
  `find_prestataire_matches(nom, prenom)`, `get_or_create_prestataire(...)` — copies directes
  de leurs équivalents patients (`crm/repo.py:146-282`), avec réutilisation de `slugify`.
- **Facture** : dataclass `Facture` ; `create_facture(prestataire_id, fichier, nom_original,
  montant, …)`, `get_facture`, `list_factures(prestataire_id, limit, offset)`,
  `count_factures_for_prestataire`, `delete_facture` (le fichier archivé est supprimé côté
  applicatif). Pas de filtre `partie` sur `documents` : `documents` reste **patient pur**.
- **Dépense** : dataclass `Depense` (incluant `montant`, `montant_regle`, `motif`) ;
  `create_depense(prestataire_id, montant, montant_regle=0, motif=…, facture_id=…, …)`
  (validation `montant > 0`, `0 ≤ montant_regle ≤ montant`, statut dérivé) ;
  `add_depense_reglement(id, montant, mode, motif, when)` (incrémente `montant_regle`,
  met à jour `date_paiement`/`mode`, **dérive le statut** ; calque enrichi de
  `mark_paiement_encaisse`, `crm/repo.py:720`) ; `list_depenses(prestataire_id, limit, offset)`,
  `count_depenses_for_prestataire`, `delete_depense`,
  `list_depenses_filtered(search, statut, limit, offset, date_from, date_to)`,
  `count_depenses(...)`, `total_depenses(...)` (sommes dû / réglé / reste) — calques de
  `list_paiements_filtered` / `count_paiements` / `total_paiements` (`crm/repo.py:806-869`).

---

## 5. Couche import/archivage `crm/generator.py`

**Pas de rendu Word pour les prestataires.** Le moteur de génération (`save_draft`,
`render_document`, `send_document`) reste **inchangé pour les patients**. On ajoute un chemin
d'**import** distinct, sans Word ni Mailjet :

- `import_facture(prestataire, src_path, *, montant=None, ...) -> Facture` :
  - **copie/archive** le fichier uploadé dans `output/prestataires/<slug>/…` (nom **horodaté**
    pour éviter toute collision avec les patients et entre imports successifs) ;
  - enregistre une ligne **`factures`** (`prestataire_id`, `fichier`, `nom_original`,
    `montant`) ; **ne touche pas à `documents`** ;
  - **n'appelle ni Word ni `send_document`** (archivage seulement).
- **Extraction IA du montant** : helper dédié (ex. `extract_montant(src_path) -> float | None`)
  appelé seulement si la case est cochée ; isolé pour pouvoir être remplacé/désactivé. En cas
  d'échec → `None` (saisie manuelle). Voir le point de conception §1.1 (service/coût).
- `build_filename` / arborescence : sous-dossier prestataire (`output/prestataires/<slug>/…`).

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
`show_patient_detail`, `crm/app.py:1329`) listant ses factures importées et ses dépenses, avec
bouton **« Importer une facture »**.

### 6.3 Import d'une facture + ligne de dépense
Nouveau dialog d'upload (PDF/image) — **pas de calque sur `_generate_dialog`** (aucune
génération Word) :
- **Sélection du fichier** → à l'enregistrement, archivage dans `output/prestataires/<slug>/…`
  (horodaté) et création d'une ligne `factures` (`import_facture`, §5).
- **Extraction IA du montant** : case **« Extraire le montant automatiquement »** (cochée par
  défaut) ; le montant extrait pré-remplit le champ **montant total** et **reste éditable**.
  Décochée / échec → saisie manuelle. (Service/coût : cf. §1.1.)
- **Ligne de dépense + règlement initial** :
  - Case **« Ajouter une ligne de dépense »** (cochée par défaut) + **montant total** (pré-rempli
    par l'IA) **+ échéance optionnelle** (`_date_field`, `crm/app.py:698`).
  - **Part déjà payée** (optionnelle) : saisie en **% ou montant exact** (toggle), bornée à
    `[0, montant]`, + champ **motif** (ex. « Avance »). Le % est converti en montant à
    l'enregistrement.
  - À l'enregistrement : si cochée et montant > 0 → `create_depense(...)` liée à la facture
    (`facture_id`), avec `montant_regle` = part payée, `motif`, et **statut dérivé**
    (`en_attente` si 0, `regle_partiellement` si 0 < payé < total, `regle` si payé ≥ total).

### 6.4 Page Finances → onglet Dépenses
Calque de `show_paiements` / `_refresh_paiements` (`crm/app.py:1609-1698`) :
- Filtres : recherche prestataire, statut (`en_attente` / `regle_partiellement` / `regle` /
  `tous`), période (date_from/date_to via `_date_field`).
- Carte récapitulative (total dû, total réglé, **reste à payer** ; calque `paie_summary`).
- Lignes : **total dû**, **réglé**, **reste à payer**, prestataire, échéance / date du dernier
  règlement, **chip** statut (« Réglé » vert / « Réglé partiellement » ambre / « À régler »
  navy), pagination `_pagination` (`crm/app.py:633`).
- Actions par ligne : **« Régler »** (icône `CHECK_CIRCLE`, ouvre la modale de versement) et
  **« Supprimer »** (icône `DELETE` / `CANCEL`), + « Ouvrir la fiche » prestataire.

### 6.5 Régler (versement) / Supprimer une dépense
- **Régler (versement partiel ou total)** : modale calquée sur `_encaisser`
  (`crm/app.py:2702-2746`), ouverte par **clic sur la ligne** (étape 5). Affiche **total dû /
  déjà réglé / reste à payer**, et propose le **nouveau montant versé** (par défaut = reste à
  payer, borné `]0, reste]`), le **mode** (`_MODE_LABELS`) et un **motif** optionnel.
  À la validation : `add_depense_reglement(...)` → `montant_regle += versement`,
  `date_paiement` = date du versement, **statut recalculé** (`regle` si solde atteint, sinon
  `regle_partiellement`). `log_audit('depense_reglee', …)` (mentionner versement vs solde) ;
  si table d'historique retenue (§3.2), y insérer une ligne.
- **Supprimer** : modale de confirmation calquée sur `_annuler_paiement`
  (`crm/app.py:2748-2774`) → `delete_depense` + `log_audit('depense_supprimee', …)`.
- Brancher la pagination/recherche/raccourcis : étendre `_page_step`, `_reset_and`,
  `_focus_search`, `_new_for_current_view` (`crm/app.py:543-626`) aux vues `prestataires`
  et `depenses`.

### 6.6 Travaux — inchangé
La page Travaux (`show_travaux`, `crm/app.py:1973`) reste **strictement patient** : `documents`
n'est pas généralisée, et les **jobs de génération/envoi** restent réservés aux notes patients.
Les **factures importées vivent dans leur propre table** (`factures`) et sont consultées depuis
la **fiche prestataire** (§6.2) et la page **Finances → Dépenses** (§6.4) — pas dans Travaux.
Aucun job n'est créé pour un import de facture.

### 6.7 Tableau de bord — dépenses & balance
Étendre `_refresh_dashboard` (`crm/app.py:889-961`) :
- Nouveaux KPI : **Dépenses réglées**, **Reste à payer** (somme des soldes non réglés),
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
| Dépense `statut` | `en_attente`, `regle_partiellement`, `regle` | « À régler », « Réglé partiellement », « Réglé » |

---

## 9. Préservation des données & migration (CRITIQUE — lire `CLAUDE.md`)

1. **Bump `SCHEMA_VERSION` 5 → 6** + étape idempotente dans `_migrate()`
   (`crm/db.py:164-253`).
2. **Migration purement additive — aucune reconstruction.** Les trois nouvelles tables
   (`prestataires`, `factures`, `depenses`, + éventuelle `depense_reglements`) sont créées via
   `CREATE TABLE IF NOT EXISTS`. **`documents` n'est jamais modifiée** (ni `ALTER`, ni
   reconstruction) : c'est le gain majeur de la table `factures` séparée — **risque quasi nul**
   sur les données patients existantes.
3. **Snapshot pré-migration** : `connect()` (`crm/db.py:215-219`) appelle déjà
   `_snapshot_before_migration()` (`crm/db.py:186-202`) **avant** `_migrate()` ; une copie
   octet pour octet du `.db` est écrite dans `backups/pre-migration/cabinet-v5-to-v6-<stamp>.db`,
   **exemptée de la purge `KEEP=10`**. Conservé tel quel (filet de sécurité même si la migration
   est additive). *(Le `CLAUDE.md` règle 3 est périmé sur ce point : le snapshot tourne bien
   avant la migration.)*
4. **Anti-downgrade** : `connect()` refuse déjà une base plus récente (`SchemaTooNewError`)
   — inchangé.
5. **Aucune opération destructive** hors `crm.reset`.
6. **Idempotence par nom de fichier** : la facture importée va dans un sous-dossier dédié
   (`output/prestataires/<slug>/`) avec un nom horodaté pour ne pas collisionner avec les notes
   patients ni entre imports (cf. règle 6).
7. **Test sur base réelle** (Windows + Word) : copier un `cabinet.db` de prod depuis
   `backups/`, lancer le build, vérifier que patients/documents/paiements existants se
   chargent et se rendent à l'identique (les nouvelles tables sont simplement vides au départ).

---

## 10. Plan de livraison (lots)

- **Lot 1 — Données** : `prestataires`, `factures`, `depenses` (+ éventuelle
  `depense_reglements`), migration v6 **additive** + snapshot pré-migration ; CRUD repo +
  tests manuels sur base de prod.
- **Lot 2 — Prestataires & import** : page Prestataires, fiche, **import de facture** (upload +
  extraction IA + archivage), ligne de dépense + règlement initial.
- **Lot 3 — Finances / Dépenses** : page Finances (onglets Paiements/Dépenses), liste filtrée,
  règlement partiel/total, suppression, pagination ; Travaux : filtre patient/prestataire.
- **Lot 4 — Tableau de bord** : KPI dépenses + graphe balance entrées/sorties.

---

## 11. Vérification (manuelle, Windows + Word requis)

1. `python crm_app.py` sur une **copie d'un `cabinet.db` de prod** : vérifier migration v6
   **additive**, snapshot `cabinet-pre-v6-*.db` créé, patients/documents/paiements **intacts**
   (table `documents` inchangée).
2. Créer un prestataire, détecter un doublon, éditer.
3. Importer une facture (PDF/image) : extraction IA du montant (cochée → pré-rempli ;
   décochée → saisie manuelle) ; saisir une avance (% puis montant) + motif ; cocher « ligne de
   dépense » avec échéance → vérifier la facture (`factures`) + la dépense liée (`facture_id`),
   le fichier archivé dans `output/prestataires/<slug>/` et le statut `regle_partiellement`.
4. Page Finances : filtrer dépenses par statut/période ; régler partiellement puis solder
   (reste à payer recalculé, statut → `regle`) ; supprimer ; pagination > 1 page.
5. Travaux : vérifier que la page reste **inchangée** (patient pur) et qu'aucun job n'est créé
   pour un import de facture.
6. Tableau de bord : KPI dépenses corrects + graphe balance entrées/sorties cohérent.

---

## 12. Fichiers concernés (implémentation ultérieure)

- `crm/db.py` — schéma + migration v6 **additive** (`prestataires`, `factures`, `depenses`) ;
  snapshot pré-migration. **`documents` inchangée.**
- `crm/repo.py` — dataclasses + CRUD Prestataire / Facture / Depense (règlement partiel).
- `crm/generator.py` — chemin d'**import** de facture prestataire (archivage + extraction IA,
  écrit dans `factures`, sans Word ni envoi) ; génération patient inchangée.
- `crm/app.py` — rail, page Prestataires, fiche, dialog **import facture + dépense**, page
  Finances (onglets), modales régler/supprimer, dashboard.
- `crm/backup.py` — snapshot pré-migration labellisé exempté de l'élagage.

> `crm/templates.py` et la table `documents` **ne sont pas modifiés** : les modèles Word et les
> notes patients restent intouchés.
