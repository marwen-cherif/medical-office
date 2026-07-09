# Cartographie de la surface UI Flet — référentiel de complétude

> **Rôle de ce document (tâches 1.1 → 1.4).** Inventaire exhaustif de la couche UI actuelle
> (`crm/app.py`, ~6320 lignes, Flet) : écrans, composants récurrents, **points de contact avec
> le moteur** Python, et **opérations longues**. Il sert de **référentiel de complétude** :
> toute cible de migration (React/Tauri, cf. `design.md`) devra **couvrir 100 % des écrans et
> des appels moteur listés ici** pour être déclarée à parité. Les numéros de ligne sont
> **indicatifs** (relevés à la rédaction) et servent de point d'entrée, pas de contrat.

## 1. Vue d'ensemble

- **Classe racine** : `CrmApp` (~L280). Corps unique `self.body` (`ft.Container`) repeint par
  écran ; navigation par `NavigationRail` à 6 destinations (~L514).
- **Machine d'état d'écran** : `self.current_view` ∈ { `dashboard`, `patients`,
  `patient_detail`, `prestataires`, `prestataire_detail`, `paiements`, `depenses`,
  `documents`, `jobs`, `job_detail`, `templates`, `mail`, `printer`, `actes` }.
- **Onglets internes mémorisés** : `detail_tab` (fiche patient), `finances_tab`,
  `travaux_tab`, `param_tab`, `detail_hist_filter`.
- **Pagination** : `PAGE_SIZE = 12` ; un index de page par liste (`patients_page`, `paie_page`,
  `dep_page`, `doc_page`, `jobs_page`, `tpl_page`, `mail_page`, `actes_page`, `pr_page`,
  `detail_docs_page`, `detail_paie_page`, …).
- **Palette / constantes** (tête de fichier) : couleurs (NAVY, TEAL, BG, SURFACE, TEXT,
  MUTED, BORDER, GREEN, RED, AMBER), maps de libellés de statut (`_STATUT_LABELS`,
  `_JOB_STATUT_LABELS`, `_JOB_ITEM_LABELS`, `_DEPENSE_STATUT_LABELS`, `_MODE_LABELS`),
  `_AUDIT_META` / `_AUDIT_FILTERS`, raccourcis clavier (`SC_NAV`, `SC_NEW`, …),
  clés `meta` (`PRINTER_KEY`, `NOTE_CAT_KEY`), options d'impression (`_PAPER_OPTIONS`,
  `_COLOR_OPTIONS`).

## 2. Écrans (14 vues) × composants × appels moteur

> Légende opérations : **🟢 sync rapide** (SQLite/fichier, < 100 ms) · **🟠 réseau court**
> (HTTP Mailjet de statut) · **🔴 long/bloquant** (Word COM, envoi Mailjet, rasterisation,
> impression GDI).

### 2.1 Tableau de bord — `show_dashboard()` (~L1296)
- **Composants** : filtre de période (`date_range`), tuiles KPI `_kpi()` en `ResponsiveRow`,
  donuts maison sur `ft.Canvas` (`_camembert()`, `_balance_chart()`), répartition par type de
  document, flux d'activité récente (audit).
- **Moteur** 🟢 : `repo.total_encaisse`, `total_creances`, `total_regle_periode`,
  `count_paiements`, `count_documents`, `count_patients`, `count_patients_new`,
  `total_depenses`, `documents_by_type`, `list_audit`.

### 2.2 Patients — liste — `show_patients()` (~L1510)
- **Composants** : `_title` + bouton « Nouveau patient », recherche (`self.search`), filtre
  (`patients_filter` : tous / avec email / avec impayés), lignes `_patient_row()` (avatar +
  identité + badge), `_pagination()`.
- **Moteur** 🟢 : `repo.list_patients`, `count_patients`, `solde_patient` (badge impayés).
- **Dialogues** : `_patient_dialog()` (création/édition + détection de doublon
  `find_matches`).

### 2.3 Patient — fiche à onglets — `show_patient_detail(patient_id)` (~L1875)
Layout responsive : identité **figée** à gauche (`_id_field` copyables, `_money_summary`),
`ft.Tabs` à droite (index mémorisé `detail_tab`).
- **Onglet 0 — Plans & actes** `_plans_actes_section()` (~L2493) : notes en attente
  (`_paie_row`), actes isolés (`_prestation_row` + barre de progression), plans repliables
  (`_plan_tile` / `ExpansionTile`), **odontogramme FDI** cliquable `_odontogramme()` (~L2649),
  carte d'acte `_acte_card()` (~L2738), menus `_actions_menu()`.
  - **Moteur** 🟢 : `repo.list_plans`, `list_prestations`, `plan_totaux`,
    `list_prestations_a_regler`, `creances_patient`, `regler_creances`, `create_plan` /
    `update_plan` / `delete_plan`, `create_prestation` / `update_prestation` /
    `delete_prestation`, `add_prestation_reglement`, `list_actes`, `log_audit`.
- **Onglet 1 — Documents** : `_grouped_docs_column()` (regroupé par catégorie,
  `ExpansionTile`), lignes `_doc_row()` avec actions contextuelles selon statut.
  - **Moteur** : `repo.list_documents`, `count_documents_for_patient`, `get_document` 🟢 ;
    **génération** `generator.render_document` 🔴 ; **envoi** `generator.send_document` 🔴 ;
    **rafraîchir statut** `generator.refresh_mail_status` 🟠 ; **ouvrir/imprimer**
    `printing.print_file` 🔴.
  - **Dialogues** : `_generate_dialog()` (~L5368, brouillon → génération, modèles
    multi-lignes via `_multiline_fields()` ~L5234), `_note_dialog()` (note d'honoraires,
    ~L5608), `_send_dialog()` (~L5981).
- **Onglet 2 — Règlements** : `_money_summary`, lignes `_encaissement_row()`.
  - **Moteur** 🟢 : `repo.list_encaissements_patient`, `count_encaissements_patient`,
    `solde_patient`.
- **Onglet 3 — Historique** `_historique_tab()` (~L2074) : chips de filtre par catégorie,
  flux d'audit regroupé par jour (`_describe_audit`, `_jour_label`, `_heure_label`).
  - **Moteur** 🟢 : `repo.list_audit_patient`.
- **Dialogues transverses fiche** : `_patient_dialog` (édition), `_plan_dialog` (~L2890),
  `_prestation_dialog` (~L3013), `_regler_dialog` (~L3136), `_paiement_dialog` (~L5648).

### 2.4 Prestataires — liste — `show_prestataires()` (~L4646)
- **Composants** : recherche `pr_search`, lignes `_prestataire_row()`, pagination.
- **Moteur** 🟢 : `repo.list_prestataires`, `count_prestataires`, `solde` agrégé.
- **Dialogues** : `_prestataire_dialog()` (~L4850, détection doublon
  `find_prestataire_matches`).

### 2.5 Prestataire — fiche — `show_prestataire_detail()` (~L4697)
- **Composants** : identité, `_money_summary`, section **Factures** (`_facture_row`), section
  **Dépenses** (`_depense_list_row`), paginations dédiées.
- **Moteur** 🟢 : `repo.list_factures`, `count_factures_for_prestataire`, `list_depenses`,
  `count_depenses_for_prestataire`, `create_depense`, `add_depense_reglement`,
  `delete_facture`, `delete_depense` ; **import** `generator.import_facture` 🟢
  (copie fichier, pas de Word) ; **ouvrir facture** `os.startfile`/`printing` 🔴.
- **Dialogues** : `_pick_and_import()` (~L4912) + `_import_facture_dialog()` (~L4928,
  extraction de montant par IA optionnelle), `_depense_dialog()` (~L5045),
  `_regler_depense()` (~L3617).

### 2.6 Finances › Paiements — `show_paiements()` (~L3367)
- **Composants** : `_finances_submenu()`, recherche, filtre statut (`paie_statut`), plage de
  dates (`paie_date_range`), `_money_summary`, lignes `_creance_row()` (mode créances) ou
  `_paie_finance_row()` (mode paiements), pagination.
- **Moteur** 🟢 : `repo.list_creances`, `count_creances`, `total_creances`,
  `list_paiements_filtered`, `count_paiements`, `total_paiements`, `total_encaisse`,
  `mark_paiement_encaisse`, `regler_creances`.

### 2.7 Finances › Dépenses — `show_depenses()` (~L3514)
- **Composants** : sous-menu, recherche, filtre statut (`dep_statut`), plage de dates,
  `_money_summary`, lignes `_depense_list_row(from_fiche=False)`, pagination.
- **Moteur** 🟢 : `repo.list_depenses_filtered`, `count_depenses`, `total_depenses`,
  `add_depense_reglement`, `delete_depense`.
- **Dialogues** : `_depense_dialog()`, `_regler_depense(back="finances")`.

### 2.8 Travaux › Documents — `show_travaux("documents")` (~L4322)
- **Composants** : `_travaux_submenu()`, recherche, filtre statut (`doc_statut`), plage de
  dates, **barre de traitement par lot** (`doc_batch_bar` : tout sélectionner + action), lignes
  sélectionnables `_doc_line_row()`, pagination.
- **Moteur** : `repo.list_documents_filtered`, `count_documents_filtered` 🟢 ; **lot**
  via jobs → `repo.create_job` / `add_job_item` / `finish_job` 🟢 pilotant
  `generator.render_document` 🔴 ou `generator.send_document` 🔴 par document.

### 2.9 Travaux › Jobs — `show_travaux("jobs")` (~L4322) + détail
- **Composants** : plage de dates, lignes `_job_row()` (compteurs + barre de progression +
  statut), détail `show_job_detail()` (~L4532) avec ligne par patient et « Relancer les
  erreurs ».
- **Moteur** 🟢 : `repo.list_jobs`, `count_jobs`, `get_job`, `list_job_items`,
  `list_failed_job_items`, `get_patient`, `get_document`, `mark_stale_jobs_interrupted`.
  Relance ⇒ rejoue `render_document`/`send_document` 🔴.

### 2.10 Paramétrage › Modèles de documents — `show_parametrage("templates")` (~L3699)
- **Composants** : sous-menu Paramétrage, sélecteur de catégorie de note, recherche, lignes
  `_template_row()` (éditer / variables / catégorie / renommer / supprimer), `_cat_pastille()`.
- **Moteur** 🟢 : `templates.list_templates`, `create_template`, `rename_template`
  (+ `repo.rename_template_meta`), `delete_template`, `open_in_word` ;
  `doc_filler.extract_placeholders` / `classify_placeholders` (lecture `.docx`) ;
  `repo.get_template_category`, `set_template_category`, `list_categories`, `upsert_category`,
  `rename_category`, `list_template_fields`, `replace_template_fields`.
- **Dialogues** : `_new_template_dialog()` (~L5739), `_rename_template_dialog()` (~L5775),
  `_set_template_category_dialog()` (~L5812), `_delete_template_dialog()` (~L5908),
  `_template_fields_dialog()` (~L3999), `_rename_category_dialog()`.

### 2.11 Paramétrage › Modèles d'email — `show_parametrage("mail")` (~L3699)
- **Composants** : recherche, lignes (nom + id Mailjet + badge défaut + étoile/éditer/supprimer).
- **Moteur** 🟢 : `repo.list_mail_templates`, `get_default_mail_template`,
  `create_mail_template`, `update_mail_template`, `delete_mail_template`,
  `set_default_mail_template`.
- **Dialogues** : `_mail_template_dialog()` (~L4123).

### 2.12 Paramétrage › Imprimante — `show_parametrage("printer")` (~L3699)
- **Composants** : carte `_printer_settings_card()` (~L3783) : choix imprimante, format
  papier (Défaut/A4/A5), couleur (Défaut/Couleur/N&B), Enregistrer / Test.
- **Moteur** : `printing.list_printers`, `default_printer` 🟢 ; `repo.get_setting` /
  `set_setting` 🟢 ; **test** `printing.print_test_page` 🔴.

### 2.13 Paramétrage › Actes (catalogue tarifé) — `show_parametrage("actes")` (~L3699)
- **Composants** : recherche, bascule « inclure inactifs », lignes `_acte_row()`
  (libellé + prix FR + actif), pagination.
- **Moteur** 🟢 : `repo.list_actes`, `count_actes`, `create_acte`, `update_acte`,
  `set_acte_actif`, `delete_acte`, `find_acte_by_libelle`.
- **Dialogues** : `_acte_dialog()` (~L4250).

## 3. Composants transverses réutilisables (à reconstruire une fois côté React)

| Composant Flet | Fonction (~ligne) | Équivalent cible (cf. `design.md` D6) |
|---|---|---|
| `NavigationRail` | `CrmApp` build (~L514) | shell + nav latérale |
| Calendrier simple FR | `_open_calendar()` (~L1043), `_date_field()` (~L1003) | `Calendar` (react-day-picker) |
| Calendrier de plage FR | `_open_range_calendar()` (~L1185), `_date_range_field()` (~L1139) | `Calendar` mode range |
| Tableau/listes denses paginées | `_pagination()` (~L938) + lignes `_*_row()` | `Table` (TanStack Table) |
| Onglets | `ft.Tabs` (fiche, finances, travaux, paramétrage) | `Tabs` (shadcn) |
| Dialogue modal + raccourcis | `_show_dialog()` (~L691), `_close_dialog()` (~L733) | `Dialog` (shadcn) |
| Carte / résumé montants | `_card()` (~L588), `_money_summary()` (~L599) | primitives + `cn()` |
| Badges de statut | maps `_*_LABELS` + chips | `Badge` (shadcn) |
| Champs copyables | `_id_field()` (~L2051) | composant identité |
| Menu d'actions | `_actions_menu()` (~L2534) | `DropdownMenu` |
| Toasts / busy | `_run_busy`, snackbars | `Sonner` + TanStack Query |
| **Odontogramme FDI** | `_odontogramme()` (~L2649) | composant **sur mesure** (pas de lib) |
| **Carte d'acte** | `_acte_card()` (~L2738), `_multiline_fields()` (~L5234) | composant **sur mesure** + `Form` |
| Donuts maison | `_camembert()`, `_balance_chart()` (Canvas) | lib de charts ou SVG |
| Helpers dates/montants FR | `_iso_to_fr`, `_fr_to_iso`, `_mask_date_fr`, `_fmt_prix` | utilitaires TS (ou côté backend) |

## 4. Opérations longues (à router via le canal d'événements — cf. `design.md` D3)

| Opération | Point d'appel UI | Fonction moteur | Nature |
|---|---|---|---|
| Génération d'un document | Documents (fiche + Travaux), jobs | `generator.render_document` → `WordSession.fill_and_export_pdf` (+ `pdf_first_page_to_jpg` si JPG) | 🔴 Word COM + export PDF + rasterisation |
| Envoi d'un email | `_send_dialog`, Travaux, jobs | `generator.send_document` → `MailjetClient.send` | 🔴 HTTP Mailjet (pièce jointe b64) |
| Rafraîchir le statut Mailjet | Documents | `generator.refresh_mail_status` → `fetch_message_status` / `fetch_message_history` | 🟠 HTTP court, polling |
| Impression | « Imprimer », test imprimante | `printing.print_file` / `print_test_page` | 🔴 GDI + pixelisation PDF |
| Traitement par lot (génération/envoi) | Travaux › Documents | jobs orchestrant les fonctions ci-dessus N fois | 🔴 long, progression par item |

> Tout le reste de l'API (`crm/repo.py`, `templates.list_*`, lectures `config`) est **🟢
> synchrone et à faible latence** : exposable directement en requête/réponse. Seules ces 5
> familles d'opérations exigent **progression + remontée d'erreur structurée** dans le contrat
> IPC (`design.md` D3 / `facade-services.md`).

## 5. Critère de complétude (gel du référentiel — tâche 1.4)

Une cible est déclarée **à parité** lorsqu'elle couvre, écran par écran :
1. **les 14 vues** du §2 (y compris détail de job et les 4 onglets de la fiche patient) ;
2. **chaque appel moteur** listé (aucune logique métier réécrite côté frontend — cf. spec
   « Réutilisation du moteur sans modification ») ;
3. **les 5 familles d'opérations longues** du §4 avec progression + erreurs visibles ;
4. **les composants transverses** du §3 (calendriers FR, odontogramme, carte d'acte,
   tableaux denses, dialogues), libellés **français** et raccourcis clavier équivalents.

Ce document est le **référentiel opposable** à la recette de parité écran par écran
(`design.md` D4 : Flet conservé comme oracle de référence pendant la cohabitation).
