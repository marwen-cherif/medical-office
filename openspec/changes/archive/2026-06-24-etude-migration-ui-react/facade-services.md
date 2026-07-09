# Façade de services backend & contrat IPC

> **Rôle de ce document (tâches 2.1, 2.2, 2.4).** Décrit la **façade de services** que le
> backend Python (FastAPI, cf. `design.md` D7) expose au frontend : **une opération par cas
> d'usage UI**, réutilisant le moteur (`src/` + `crm/` hors `app.py`) **sans le modifier** ;
> le **contrat d'échange** (formats, codes d'erreur, progression) ; et la **démonstration de
> préservation des invariants** de `CLAUDE.md`. Le catalogue dérive directement du référentiel
> (`cartographie.md`) : chaque appel moteur cartographié se projette en une opération de façade.

## 1. Principes

- **Frontière nette.** Le frontend ne contient **aucune logique métier** : il appelle des
  opérations de haut niveau (verbe métier), le backend orchestre `repo`/`generator`/
  `templates`/`printing`/`mailer`. Le moteur n'est **pas modifié** ; la façade est une fine
  couche d'adaptation (`crm/server.py`, à créer ultérieurement) au-dessus des fonctions
  existantes.
- **Granularité = cas d'usage, pas table.** On expose « générer un document », « régler en
  cascade », « importer une facture » — pas un CRUD SQL générique. Cela garde les règles
  (idempotence, cascade, snapshots) **côté Python**.
- **Connexion gérée par le backend.** Le paramètre `conn` des fonctions `repo.*` n'apparaît
  **jamais** dans le contrat : le backend ouvre/possède la connexion SQLite (`db.connect`).
- **Typage de bout en bout.** Schéma OpenAPI généré par FastAPI → **client TypeScript généré**
  (`openapi-typescript`/`orval`), consommé par TanStack Query (cf. `design.md` D6/D7).

## 2. Catalogue des opérations (une par cas d'usage UI)

> Notation : **R** = requête/réponse synchrone (HTTP) ; **J** = opération longue suivie par
> **job + flux d'événements** (cf. §4). Les opérations R s'appuient sur des fonctions 🟢 du
> moteur (cf. `cartographie.md` §4).

### 2.1 Tableau de bord
| Opération | Type | Moteur réutilisé |
|---|---|---|
| `dashboard.summary(periode)` | R | `repo.total_encaisse/total_creances/total_regle_periode/count_*/total_depenses/documents_by_type` |
| `dashboard.activite(periode, limit)` | R | `repo.list_audit` |

### 2.2 Patients
| Opération | Type | Moteur |
|---|---|---|
| `patients.list(search, filtre, page)` | R | `repo.list_patients` + `count_patients` |
| `patients.get(id)` | R | `repo.get_patient` + `solde_patient` |
| `patients.matches(nom, prenom)` | R | `repo.find_matches` (doublons) |
| `patients.create(data)` / `patients.update(id, data)` | R | `repo.create_patient` / `update_patient` (+ `log_audit`) |

### 2.3 Plans, actes, règlements (fiche patient)
| Opération | Type | Moteur |
|---|---|---|
| `plans.list(patient_id)` / `create` / `update` / `delete` | R | `repo.list_plans/create_plan/update_plan/delete_plan`, `plan_totaux` |
| `prestations.list(patient_id, plan_id?)` | R | `repo.list_prestations` |
| `prestations.create/update/delete` | R | `repo.create_prestation/update_prestation/delete_prestation` (+ `log_audit`) |
| `prestations.regler(id, versement, mode)` | R | `repo.add_prestation_reglement` |
| `creances.patient(patient_id)` / `creances.regler(patient_id, versement)` | R | `repo.creances_patient` / `regler_creances` (cascade) |
| `encaissements.patient(patient_id, page)` | R | `repo.list_encaissements_patient` + count |
| `actes.referentiel(search, inclure_inactifs, page)` | R | `repo.list_actes` + count |
| `historique.patient(patient_id, filtre, limit)` | R | `repo.list_audit_patient` |

### 2.4 Documents (génération / envoi / impression)
| Opération | Type | Moteur |
|---|---|---|
| `documents.list(patient_id?, filtres, page)` | R | `repo.list_documents` / `list_documents_filtered` (+ count) |
| `documents.saveDraft(patient_id, template, variables, format)` | R | `generator.save_draft` / `update_draft` (rapide, sans Word) |
| **`documents.generate(document_id)`** | **J** | `generator.render_document` 🔴 (Word COM + PDF + JPG) |
| **`documents.send(document_id, template_id?)`** | **J** | `generator.send_document` 🔴 (Mailjet) |
| `documents.refreshStatus(document_id)` | R(🟠) | `generator.refresh_mail_status` |
| **`documents.print(document_id, options)`** | **J** | `printing.print_file` 🔴 (GDI) |
| `documents.open(document_id)` | R | renvoie le chemin fichier (ouverture côté coquille) |
| `documents.delete(document_id)` | R | `repo.delete_document` |

### 2.5 Jobs (traitement par lot)
| Opération | Type | Moteur |
|---|---|---|
| **`jobs.run(kind, doc_type, document_ids, params)`** | **J** | `repo.create_job/add_job_item/finish_job` pilotant `render_document`/`send_document` 🔴 |
| `jobs.list(periode, page)` / `jobs.get(id)` / `jobs.items(id)` | R | `repo.list_jobs/get_job/list_job_items` |
| `jobs.retryFailed(id)` | J | `repo.list_failed_job_items` + rejeu |

### 2.6 Finances
| Opération | Type | Moteur |
|---|---|---|
| `paiements.list(filtres, page)` / `paiements.encaisser(id, mode)` | R | `repo.list_paiements_filtered`, `mark_paiement_encaisse` |
| `depenses.list(filtres, page)` / `create` / `regler` / `delete` | R | `repo.list_depenses_filtered`, `create_depense`, `add_depense_reglement`, `delete_depense` |

### 2.7 Prestataires & factures
| Opération | Type | Moteur |
|---|---|---|
| `prestataires.list/get/create/update` | R | `repo.list_prestataires/get_prestataire/...` |
| `factures.list(prestataire_id, page)` / `delete` | R | `repo.list_factures` / `delete_facture` |
| `factures.import(prestataire_id, fichier, montant, libelle)` | R | `generator.import_facture` (copie fichier, pas de Word) |

### 2.8 Paramétrage
| Opération | Type | Moteur |
|---|---|---|
| `templates.list/create/rename/delete` | R | `templates.*` (+ `repo.rename_template_meta`) |
| `templates.openInWord(name)` | R | `templates.open_in_word` (lance Word côté backend) |
| `templates.placeholders(name)` | R | `doc_filler.extract_placeholders` / `classify_placeholders` |
| `templates.fields.get/replace(name)` | R | `repo.list_template_fields` / `replace_template_fields` |
| `categories.list/upsert/rename` + `templates.setCategory` | R | `repo.list_categories/upsert_category/rename_category/set_template_category` |
| `mailTemplates.list/create/update/delete/setDefault` | R | `repo.*_mail_template` |
| `printers.list` / `printers.test(name)` | R / J | `printing.list_printers` / `print_test_page` 🔴 |
| `settings.get/set(key)` | R | `repo.get_setting` / `set_setting` |
| `actes.create/update/setActif/delete` | R | `repo.*_acte` |

## 3. Contrat d'échange (formats)

- **Transport** : HTTP/1.1 sur `127.0.0.1`, JSON UTF-8. Port **éphémère** choisi par le
  backend au démarrage et transmis au frontend (cf. `design.md` D3/D5) ; liaison **loopback
  uniquement** ; **jeton de session** partagé (en-tête `Authorization`) émis au lancement.
- **Requête** : corps JSON typé (généré depuis l'OpenAPI). Montants en **nombres** (calculs
  côté Python) ; dates en **ISO `AAAA-MM-JJ`** sur le fil — le formatage FR
  (`_fmt_prix`, `_iso_to_fr`) reste un détail de présentation, dérivable côté front ou fourni
  par le backend.
- **Réponse succès** : `200` + objet métier (mêmes champs que les dataclasses `repo.*`).
  Listes paginées : `{ items: [...], total, page, pageSize }`.
- **Pagination** : `page`/`pageSize` (défaut `PAGE_SIZE = 12`) → `limit`/`offset` côté `repo`.

## 4. Opérations longues : progression & statut asynchrone (tâche 2.2)

Les 5 familles 🔴/🟠 (`cartographie.md` §4) ne bloquent pas la requête HTTP :

1. **Démarrage** : `POST` de l'opération **J** → `202 Accepted` + `{ jobId }` (réutilise le
   modèle `jobs` existant : `repo.create_job` / `add_job_item` / `finish_job`).
2. **Progression** : le frontend s'abonne à un **canal d'événements** (`GET /events/{jobId}`
   en **SSE**, ou WebSocket — cf. `design.md` D3) : événements `progress`
   `{ done, total, ok, skipped, errors }`, puis `item` par document, puis `done`/`error`.
3. **Exécution** : chaque opération longue tourne dans un **worker** (pool de threads ; Word
   COM exige l'initialisation COM **dans le thread worker**, pas dans la boucle ASGI). La
   garde mono-job existante (`_job_running`) devient une **sérialisation côté backend**.
4. **Reprise** : `mark_stale_jobs_interrupted` au démarrage du backend (déjà présent) couvre
   le crash d'un job en cours — **inchangé**.

## 5. Codes d'erreur (tâche 2.2)

Les erreurs moteur connues sont remontées en **codes structurés** (et non en stack-trace),
présentés à l'utilisateur en français par le frontend :

| Code | Origine moteur | Présentation suggérée |
|---|---|---|
| `WORD_UNAVAILABLE` | `WordSession.__enter__` (Word absent / COM KO) | « Microsoft Word est introuvable ou indisponible. » |
| `GENERATION_FAILED` | `render_document` (statut `erreur`) | message d'erreur du document + action « Réessayer » |
| `MAIL_SEND_FAILED` | `send_document` (statut `erreur_envoi`) | erreur Mailjet + action « Renvoyer » |
| `MAIL_STATUS_FAILED` | `refresh_mail_status` (HTTP KO) | non bloquant, conserve le dernier statut |
| `PRINTER_NOT_FOUND` / `PRINT_FAILED` | `printing.print_file` | « Imprimante introuvable / impression échouée. » |
| `TEMPLATE_INVALID` | `expand_table_rows` (multi lignes-modèles, fusion verticale, tableau imbriqué) | erreur explicite côté éditeur de modèle |
| `SCHEMA_TOO_NEW` | `db.connect` (`SchemaTooNewError`) | blocage au lancement : base touchée par une version plus récente |
| `VALIDATION_ERROR` | dataclasses/règles (`montant < regle`, FDI, doublons) | message de champ |

Le mapping statut↔libellé/couleur existant (`_STATUT_LABELS`, `_JOB_STATUT_LABELS`, …) est
**repris côté frontend** (cf. `cartographie.md` §1), pas réinventé.

## 6. Préservation des invariants (tâche 2.4 — démonstration)

L'architecture sidecar (`design.md` D1) **garde tous les invariants côté backend Python
inchangé** :

| Invariant `CLAUDE.md` | Comment il est préservé |
|---|---|
| **Windows-only / Word COM** | `render_document` reste piloté par `WordSession` (COM) dans le sidecar Windows ; le frontend n'y touche pas. La cible **ne supprime pas** Word COM (hors périmètre). |
| **Propriété des données** | `data/cabinet.db`, `output/`, `templates/`, `config.ini` restent **possédés et lus/écrits par le backend** ; le frontend ne voit que des opérations. Emplacement « à côté de l'exe » conservé (`db.app_dir`). |
| **Idempotence par nom de fichier** | `generator.build_filename` + court-circuit si fichier/ligne `documents` existe : **logique inchangée**, exécutée dans la façade, jamais côté front. |
| **Migrations & anti-downgrade** | `db.connect` (schéma, `_migrate()` idempotent, `SCHEMA_VERSION = 11`, `SchemaTooNewError`) s'exécute **au démarrage du backend** — identique à aujourd'hui. |
| **Backup au démarrage** | `backup.backup_db()` (rotation `KEEP=10`) appelé par le backend avant ouverture — **inchangé** (cf. règle « back up BEFORE migrating »). |
| **Snapshots figés** | `documents.categorie`, `documents.montant` (affichage), `__lignes__` JSON, prix d'acte snapshot : **calculés/figés côté Python**, le contrat ne réexpose pas de recalcul côté front. |
| **Secrets** | `config.ini` (clés Mailjet) reste **côté backend**, jamais transmis au frontend ; le contrat n'expose aucune clé. |

**Conclusion** : la frontière IPC déplace **uniquement la présentation**. Les règles
data-affectantes (idempotence, migrations, backup, snapshots, secrets) restent dans le moteur
Python servi en sidecar — la cible **ne casse aucun invariant** et la démonstration est
opposable écran par écran via `cartographie.md` (recette de parité, `design.md` D4).
