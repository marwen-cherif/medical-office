## 1. Schéma & persistance (crm/db.py, crm/repo.py)

- [ ] 1.1 Ajouter la table `rappels` via `CREATE TABLE IF NOT EXISTS` (colonnes : `id`,
  `type`, `patient_id` nullable, `document_id` nullable, `titre`, `message`, `echeance`,
  `etat`, `created_at`, `notified_at` nullable, `sent_at` nullable) dans `crm/db.py`
- [ ] 1.2 Bump `SCHEMA_VERSION` et ajouter une étape `_migrate()` idempotente (guardée par
  un check d'existence) créant la table sur une DB existante peuplée
- [ ] 1.3 Prendre un snapshot pré-migration labellisé (`cabinet-pre-v<N>-…db`) **avant**
  la migration, exempté du prune `KEEP=10` (cf. CLAUDE.md « Back up BEFORE migrating »)
- [ ] 1.4 Vérifier l'anti-downgrade (`SchemaTooNewError`) avec la nouvelle version
- [ ] 1.5 Ajouter la dataclass `Rappel` + CRUD dans `crm/repo.py` : créer, lister filtré
  par état (à venir / dus / traités), récupérer les rappels dus (`planifie` &
  `echeance<=maintenant`), transitions d'état (mise en file, notifié, envoyé, traité,
  annulé)
- [ ] 1.6 Tester migration + CRUD sur une copie d'un `cabinet.db` de prod (depuis
  `backups/`)

## 2. Logique métier des rappels (crm/)

- [ ] 2.1 Créer un module `crm/rappels.py` (ou similaire) : sélection des rappels dus,
  transition atomique `planifie` → `du`/`a_envoyer` avec horodatage `notified_at`,
  idempotence (ignorer `du`/`a_envoyer`/`envoye`/`traite`/`annule`)
- [ ] 2.2 Normalisation du numéro de téléphone patient au format international (indicatif
  pays par défaut paramétrable, cf. open question +216), avec validation
- [ ] 2.3 Construction du lien WhatsApp `https://wa.me/<numero>?text=<message_urlencodé>`
  et ouverture (desktop : navigateur/WhatsApp ; web : ouverture côté praticien)
- [ ] 2.4 Validation à la création : `message_patient` exige patient + numéro exploitable ;
  refus explicite sinon

## 3. Mode service de fond (headless)

- [ ] 3.1 Ajouter un point d'entrée headless (`--service` dans `crm_app.py` traité avant
  le GUI, et/ou `python -m crm.service`) : ouvre la DB, traite les rappels dus, sort —
  sans Flet, sans Word, sans Mailjet
- [ ] 3.2 Émettre une notification Windows à l'échéance (toast `win32`/pywin32 déjà
  embarqué) pour alertes internes (`du`) et messages patients mis en file (`a_envoyer`)
- [ ] 3.3 Garantir l'idempotence multi-exécutions (pas de re-notification, pas de doublon
  en file) en réutilisant les transitions d'état de 2.1

## 4. Tâche planifiée Windows

- [ ] 4.1 Créer/mettre à jour la tâche planifiée Windows via `schtasks` appelant l'exe en
  mode `--service` à intervalle régulier (défaut 15–30 min)
- [ ] 4.2 Installer/mettre à jour la tâche au démarrage de l'app (idempotent) et permettre
  son activation/désactivation
- [ ] 4.3 Afficher l'état de la tâche planifiée dans Paramétrage (présente/active)

## 5. Interface CRM (crm/app.py)

- [ ] 5.1 Nouvel écran/section « Rappels » : liste filtrable par état (à venir / dus /
  traités) avec patient, document, échéance, type
- [ ] 5.2 Formulaire de création/édition d'un rappel (type, patient/document optionnels,
  titre, message, échéance ; échéances relatives +1 mois / +2 mois)
- [ ] 5.3 Bouton « Planifier un rappel » après envoi d'un document, pré-rempli avec le
  patient et le document rattachés et une échéance par défaut
- [ ] 5.4 File WhatsApp : liste des rappels `a_envoyer` avec action « Envoyer via
  WhatsApp » (ouverture `wa.me`) puis marquage `envoye` ; gestion du numéro invalide
- [ ] 5.5 Présentation des rappels dus au démarrage (alertes internes `du` + file
  WhatsApp `a_envoyer`) avec actions (envoyer / marquer traité)
- [ ] 5.6 Édition tant que non envoyé/traité et annulation (`annule`) empêchant toute
  notification/mise en file ultérieure
- [ ] 5.7 Vérification des rappels dus aussi à l'ouverture de l'app (filet de sécurité si
  la tâche planifiée est absente/désactivée)

## 6. Configuration, build & validation

- [ ] 6.1 Paramètres `config.ini` (activation du service, intervalle de vérification,
  indicatif pays par défaut)
- [ ] 6.2 Vérifier le packaging PyInstaller (`crm-desktop.spec`, `crm-web.spec`,
  `build-crm.bat`) : mode `--service` inclus, dépendances de notification embarquées
- [ ] 6.3 Documenter dans CLAUDE.md la fonctionnalité Rappels, le mode service et la tâche
  planifiée
- [ ] 6.4 Recette manuelle sur Windows : création d'un rappel, échéance atteinte app
  fermée → notification + mise en file, envoi WhatsApp en un clic, annulation, rattrapage
  après poste éteint ; validation sur une copie de DB de prod
