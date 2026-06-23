## Context

La fiche patient est rendue par `show_patient_detail` (`crm/app.py`, ~L1830-1923) : une
unique `ft.Column` scrollable empilant six blocs (en-tête, carte infos, règlements,
plans & actes, documents). Les helpers existants — `_grouped_docs_column`,
`_plans_actes_section`, `_money_summary`, `_encaissement_row`, `_doc_row`, `_plan_tile`,
`_prestation_row`, `_kv` / `_kv_copy`, `_pagination` — restent réutilisables : la refonte
**réagence** ces briques, elle ne les réécrit pas.

Côté données, la table `audit_log(id, ts, action, detail)` (SCHEMA v10) et les fonctions
`repo.log_audit(conn, action, detail)` / `repo.list_audit(conn, limit, date_from, date_to)`
existent déjà, et plusieurs appels `log_audit` sont disséminés dans `app.py`. Mais le
journal est **global** : pas de colonne `patient_id`, `detail` en texte libre
(`"patient_id=5"`), couverture partielle, et aucune UI ne l'affiche.

Contraintes fortes (CLAUDE.md) : base de production existante et peuplée ; migrations
**additives/idempotentes** uniquement ; bump `SCHEMA_VERSION` + étape `_migrate()` gardée
par `_column_exists` ; snapshot pré-migration ; anti-downgrade ; aucune opération
destructive hors `crm.reset`. Windows + Flet desktop/web, même `crm/app.py`.

## Goals / Non-Goals

**Goals:**

- Réagencer la fiche en deux zones : colonne d'identité figée à gauche + contenu en onglets
  (Plans & actes / Documents / Règlements / Historique), sans perte de fonctionnalité.
- Rendre le journal d'audit exploitable **par patient** : colonne `patient_id` + `detail`
  structuré (JSON), et journalisation systématique et enrichie des événements clés.
- Afficher l'historique : flux antichronologique groupé par jour, filtrable par catégorie,
  avec détail avant→après pour les mises à jour de fiche.

**Non-Goals:**

- Modifier le moteur `src/` (Word/Mailjet/PyMuPDF) ou le schéma des plans/actes/documents.
- Modifier les exigences des capabilities `plans-de-traitement` / `referentiel-actes`
  (seul leur emplacement d'affichage change).
- Export, purge, rétention ou pagination « infinie » du journal (au-delà d'une limite
  raisonnable), filtrage par date dans l'UI patient, multi-utilisateur/auteur des actions.
- Backfill rétroactif des anciennes lignes `audit_log` vers un `patient_id`.

## Decisions

### D1 — Disposition : `ft.Row` [identité figée | onglets] plutôt que refonte en pages

La page devient `ft.Row([identite, contenu], vertical_alignment=START)` où `identite` est
un `Container` de largeur fixe (~280-320 px) et `contenu` un `Container(expand=True)`
hébergeant un `ft.Tabs`. Le scroll passe du niveau page au niveau **contenu d'onglet**
(chaque onglet est une `Column(scroll=AUTO)`), pour que l'identité reste figée.

- *Pourquoi* : répond directement au « espace perdu en haut » et aux « blocs éparpillés » ;
  garde le contexte patient visible ; réutilise les helpers de blocs tels quels dans les
  onglets. Alternative écartée : conserver l'empilement vertical avec ancres — ne règle ni
  l'espace perdu ni la dispersion. Alternative écartée : pages/routes séparées — perte du
  contexte patient et navigation plus lourde.
- *Web* : `ft.Tabs` et `ft.Row` fonctionnent à l'identique en mode web. Sur fenêtre étroite,
  prévoir un seuil de largeur en-dessous duquel l'identité repasse au-dessus du contenu
  (dégradation gracieuse), à valider visuellement.

### D2 — `audit_log` : enrichir la table existante (pas de nouvelle table)

Ajout de deux colonnes nullables à `audit_log` : `patient_id INTEGER` (référence logique
vers `patients.id`, **sans** contrainte FK pour ne pas bloquer les lignes globales/orphelines
et préserver la nature best-effort) et conservation de `detail` qui hébergera désormais un
**JSON**. Ajout d'un index `idx_audit_patient (patient_id, id DESC)` pour la lecture par
patient.

- *Pourquoi réutiliser la table* : migration plus simple, conserve l'historique global déjà
  écrit, `list_audit` global (Paramétrage) continue de fonctionner. Alternative écartée :
  nouvelle table `patient_events` — duplication, double chemin d'écriture, migration des
  appels existants.
- *Pourquoi pas de FK sur `patient_id`* : `log_audit` est best-effort et certaines lignes
  sont globales (`patient_id` NULL) ; une FK + `ON DELETE` compliquerait la suppression de
  patient et le caractère « ne jamais échouer ».

### D3 — `detail` structuré JSON, rétrocompatible à la lecture

`detail` stocke un JSON (`{"...": ...}`) à l'écriture. La lecture (`list_audit` /
rendu UI) tente `json.loads` et **retombe** sur l'affichage brut si ce n'est pas du JSON
(anciennes lignes `"patient_id=5"`). Convention de types d'action stables en `snake_case`
(ex. `fiche_creee`, `fiche_modifiee`, `plan_cree`, `plan_modifie`, `plan_supprime`,
`acte_ajoute`, `acte_modifie`, `acte_supprime`, `acte_regle`, `document_genere`,
`note_honoraires_generee`, `document_envoye`).

- *Pourquoi JSON* : permet le détail avant→après et l'enrichissement (modèle, montant,
  dents) sans colonnes dédiées. Alternative écartée : colonnes typées — rigide, migrations
  à répétition.

### D4 — Signatures `repo` : surcharges rétrocompatibles

`log_audit(conn, action, detail="", *, patient_id=None)` — `detail` accepte une chaîne
(rétrocompat) ou un dict sérialisé en JSON par la fonction. Nouvelle
`list_audit_patient(conn, patient_id, limit=...)` dédiée à l'onglet. `update_patient`
calcule le diff des champs (nom, prénom, email, téléphone, date_naissance, adresse, notes)
**avant** l'UPDATE et renvoie/journalise la liste `{champ: [avant, après]}`.

- *Pourquoi un diff dans `repo`* : `update_patient` est le seul point qui connaît l'ancien
  et le nouvel état de façon fiable ; centraliser y évite d'oublier des champs côté UI.
  Le mapping type d'action → catégorie/icône/libellé vit dans `app.py` (couche présentation,
  à côté des autres maps existantes).

### D5 — Migration v11

`SCHEMA_VERSION` 10 → 11. Étape `_migrate()` idempotente, gardée par `_column_exists`, qui
ajoute `audit_log.patient_id` puis l'index. Snapshot pré-migration labellisé
(`cabinet-pre-v11-…db`, exempté du prune `KEEP=10`) pris **avant** la migration, comme exigé
par CLAUDE.md. Anti-downgrade déjà assuré par `connect()` (`SchemaTooNewError`).

### D6 — Rendu de l'onglet Historique

Nouvel helper `_historique_tab(patient_id)` : lit via `list_audit_patient`, regroupe par
jour (« Aujourd'hui » / « Hier » / date), rend chaque entrée (icône + libellé + heure), et
pour `fiche_modifiee` déplie les lignes `champ : avant → après`. Une rangée de filtres
(SegmentedButton/Chips : Tous, Fiche, Plans, Actes, Documents, Règlements) re-filtre la
liste en mémoire. Limite de lecture raisonnable (ex. 200) avec mention si tronqué.

## Risks / Trade-offs

- **Régression fonctionnelle de la fiche (gros fichier `app.py`)** → réutiliser les helpers
  existants sans les modifier ; checklist de parité (chaque action de la fiche actuelle
  retrouvée dans un onglet) ; test manuel sur une copie de `cabinet.db` de production.
- **Couverture incomplète des événements** (appels `log_audit` oubliés) → recenser tous les
  points de mutation dans `repo`/`app` (création/édition/suppression patient, plan, acte,
  règlement, génération, envoi) et cocher chacun dans `tasks.md`.
- **`detail` JSON volumineux / valeurs sensibles** → ne consigner que les champs métier
  nécessaires (pas de secrets) ; valeurs longues tronquées à l'affichage.
- **Lisibilité sur fenêtre étroite (web)** → seuil de bascule identité/contenu et
  vérification visuelle desktop + web.
- **Migration sur base peuplée** → étape additive idempotente + snapshot pré-migration +
  test sur DB réelle issue de `backups/` avant livraison (porte manuelle, pas de CI).

## Migration Plan

1. Prendre le snapshot pré-migration `cabinet-pre-v11-…db` (exempt du prune) avant `connect()`
   ne migre.
2. Migration v11 : `ALTER TABLE audit_log ADD COLUMN patient_id INTEGER` (gardé par
   `_column_exists`) + `CREATE INDEX IF NOT EXISTS idx_audit_patient ON audit_log(patient_id, id DESC)`.
3. Enrichir `repo.log_audit` / ajouter `list_audit_patient` ; brancher `patient_id` + detail
   JSON sur tous les points de mutation ; calculer le diff dans `update_patient`.
4. Refondre `show_patient_detail` (identité + `ft.Tabs`) et ajouter `_historique_tab`.
5. **Rollback** : l'ancien binaire rouvre la base (colonne `patient_id` simplement ignorée) ;
   restauration possible depuis le snapshot pré-v11 en cas de problème.
6. Valider sur une copie de production : patients/documents/plans/actes/règlements chargent
   et s'affichent ; historique peuplé par de nouvelles actions ; anciennes lignes tolérées.

## Open Questions

- Seuil de largeur exact pour faire basculer l'identité au-dessus du contenu en mode web —
  à fixer visuellement.
- L'onglet par défaut doit-il être « Plans & actes » (retenu) ou un futur « Aperçu » ? Hors
  périmètre pour l'instant.
- Faut-il mémoriser le dernier onglet/filtre consulté entre deux ouvertures de fiche ?
  (Confort, non bloquant — par défaut : non.)
