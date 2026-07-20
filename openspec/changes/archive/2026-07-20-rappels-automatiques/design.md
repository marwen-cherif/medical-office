## Context

Le CRM est une application desktop/web React/Tauri avec un backend FastAPI (`crm_server.py`
/ `crm/server.py`) et une base SQLite (`data/cabinet.db`). Le backend réutilise le moteur
partagé `src/` (Word COM, Mailjet, PyMuPDF) et expose ses cas d'usage via des routeurs
FastAPI (`crm/routers/`). L'application n'est **pas allumée en permanence** : c'est un
outil de bureau ouvert ponctuellement par le praticien.

Le besoin métier : au moment d'envoyer un document (ou à tout moment), planifier soit une
**alerte interne** pour le praticien, soit un **message WhatsApp au patient** à une date
future, rédigé à l'avance, avec une notification fiable à l'échéance même application
fermée.

Contraintes structurantes :
- **Préservation des données (CLAUDE.md)** : schéma additif/expand-only, bump
  `SCHEMA_VERSION` + `_migrate()` idempotente guardée par `_column_exists`, snapshot
  pré-migration, anti-downgrade.
- **WhatsApp `wa.me`** : seul canal pour les rappels patients. Texte 100 % libre, envoi
  assisté (ouverture de WhatsApp pré-rempli, clic manuel du praticien). Indépendant du
  feature flag `whatsapp_api_enabled` (Meta Cloud API) qui ne concerne que l'envoi de
  documents via templates.
- **Numéros WhatsApp** : un patient peut avoir plusieurs numéros dans `patient_phones`
  avec `is_whatsapp = 1`. Si un seul → ouverture directe du lien `wa.me`. Si plusieurs →
  sélecteur de numéro présenté au praticien avant ouverture.
- **Settings rappels** : stockés dans la table `meta` (même pattern que les autres
  settings), accessibles et modifiables via la section « Rappels » du Paramétrage UI.

## Goals / Non-Goals

**Goals:**

- Stocker des rappels datés (alerte interne ou message patient WhatsApp) rattachables à un
  patient/document, dans SQLite, de façon additive et sûre pour la prod.
- Déclencher/notifier les rappels échus **même application fermée**, via une tâche
  planifiée Windows exécutant un processus headless distinct du serveur FastAPI.
- Émettre une **notification Windows 11 native** par rappel échu (configurable, activée
  par défaut). Rattrapage après interruption : N notifications individuelles.
- À l'échéance, mettre les messages patients en file (`a_envoyer`) et permettre leur
  envoi **en un clic** via `wa.me` (texte libre pré-rempli).
- Exposer une **icône cloche** persistante dans l'interface React avec badge numérique
  et panneau d'actions (ignorer / ouvrir fiche patient / envoyer WhatsApp).
- Exposer un **onglet Rappels** sur la fiche patient.
- Exposer une **section Rappels dans le Paramétrage** (notifications, intervalle tâche,
  indicatif pays, état tâche planifiée).

**Non-Goals:**

- Aucun email / Mailjet dans cette fonctionnalité.
- Pas d'envoi WhatsApp automatique via Meta Cloud API (texte libre impossible hors fenêtre
  24 h). L'intégration par modèles approuvés est documentée comme évolution future.
- Pas de SMS ni d'autres canaux.
- Pas de récurrence complexe (rappels répétitifs) en v1 — échéance ponctuelle uniquement.
- Pas de modification du moteur `src/`.

## Decisions

### D1 — Une table `rappels` unique, polymorphe par `type`

Une seule table couvre les deux types. Colonnes principales :
`id`, `type` (`alerte_interne` | `message_patient`), `patient_id` (nullable),
`document_id` (nullable), `titre`, `message` (texte libre, destiné au patient),
`echeance` (ISO), `etat`, `lu` (INTEGER DEFAULT 0), `created_at`, `notified_at`
(nullable), `sent_at` (nullable).

**Cycle de vie des états (`etat`) :**
- `planifie` → (tâche planifiée à l'échéance) → `du` (alerte interne) ou `a_envoyer`
  (message patient)
- `a_envoyer` → (ignoré depuis la cloche) → `lu` via colonne `lu = 1` ; l'état reste
  `a_envoyer` mais le rappel sort du badge et du panneau cloche
- `a_envoyer` / `lu = 1` → (envoi `wa.me` confirmé) → `envoye`
- `du` → (marqué traité manuellement) → `traite`
- `envoye` → (marqué traité manuellement) → `traite`
- `planifie` → (annulation manuelle) → `annule`

La colonne `lu` est un booléen additionnel : elle n'est pas un état `etat` à part entière
mais un flag de lecture qui permet de distinguer "en attente d'envoi, vu" de "en attente
d'envoi, non vu" sans changer le flux fonctionnel. Le badge cloche compte `du` +
`a_envoyer` où `lu = 0`.

*Alternative écartée* : ajouter `lu` comme valeur de `etat`. Rejeté car `lu` ne
représente pas une étape du cycle métier (le rappel reste à envoyer), et mélanger
lecture UI et état métier complexifie les requêtes et la logique de transition.

### D2 — Processus headless distinct du serveur FastAPI

Un point d'entrée headless (`python -m crm.service` ou `Cabinet-CRM.exe --service`)
distinct de `crm_server.py` (Uvicorn/FastAPI). Il ouvre la DB via `crm/db.connect()`,
lit les rappels `planifie` dont `echeance <= maintenant`, fait passer chacun à
`du`/`a_envoyer`, émet une notification Windows 11 si activée, et sort. Il ne démarre
ni Uvicorn, ni Flet, ni Word, ni Mailjet.

Une **tâche planifiée Windows** (créée via `schtasks`) l'exécute à intervalle régulier
(défaut 15 min, paramétrable dans le Paramétrage).

*Pourquoi pas `--service` dans `crm_server.py`* : `crm_server.py` démarre Uvicorn et
charge tous les routeurs — trop lourd pour une exécution de fond de quelques secondes.
Un module dédié `crm/service.py` garde la dépendance minimale (db + repo + notification).

### D3 — Idempotence par état + transition atomique

Le service ne traite que les rappels `planifie` dont l'échéance est dépassée. La
transition `planifie` → `du`/`a_envoyer` est effectuée en une transaction avec
horodatage de `notified_at`. Un rappel déjà `du`/`a_envoyer`/`lu`/`envoye`/`traite`/
`annule` est ignoré : pas de re-notification, pas de doublon en file, même si la tâche
se chevauche ou rejoue.

**Rattrapage après interruption** : si N rappels sont en retard, le service les traite
tous et émet N notifications individuelles (une par rappel échu). Pas de regroupement.

### D4 — Canal patient : WhatsApp assisté via `wa.me`, indépendant de la Meta Cloud API

Le feature flag `whatsapp_api_enabled` ne bloque pas les rappels : il ne concerne que
`/documents/{id}/send-whatsapp` (envoi via Meta Cloud API + templates). Le lien `wa.me`
est construit côté frontend à partir du numéro normalisé et du texte du rappel, sans
passer par l'API Meta.

Sélection du numéro :
- Si le patient a **1 seul** numéro `is_whatsapp = 1` → ouverture directe de `wa.me`
- Si le patient a **2+** numéros `is_whatsapp = 1` → sélecteur de numéro présenté avant
  l'ouverture (même logique UX que l'envoi de documents)

Normalisation au format international : indicatif pays par défaut `+216` (paramétrable
dans `meta` / Paramétrage UI), appliqué aux numéros locaux sans préfixe international.
Un numéro non normalisable bloque l'action avec un message d'erreur explicite.

### D5 — Migration additive + snapshot pré-migration

`CREATE TABLE IF NOT EXISTS rappels (...)`, bump `SCHEMA_VERSION`, étape `_migrate()`
idempotente. Conformément à CLAUDE.md, snapshot pré-migration labellisé avant migration,
exempté du prune `KEEP=10`. Aucune colonne/table existante modifiée.

### D6 — Settings rappels dans la table `meta`

Les quatre settings rappels sont stockés dans `meta` (même pattern que `printer_name`,
`whatsapp_phone_number_id`, etc.) :

| Clé `meta`                    | Défaut  | Description                              |
|-------------------------------|---------|------------------------------------------|
| `rappels_notifs_enabled`      | `true`  | Notifications Windows 11 activées        |
| `rappels_scheduler_interval`  | `15`    | Intervalle tâche planifiée (minutes)     |
| `rappels_default_country`     | `+216`  | Indicatif pays pour normalisation numéro |

L'état de la tâche planifiée (présente/active/inactive) est lu depuis `schtasks /query`
au chargement de la section Paramétrage — lecture seule, non stocké en DB.

*Pourquoi `meta` et non `config.ini`* : le processus headless lit déjà la DB pour les
rappels — lire les settings au même endroit évite une dépendance à `config.ini` depuis
le service. Le Paramétrage UI écrit déjà dans `meta` pour les autres settings.

### D7 — Icône cloche et panneau notifications dans l'interface React

La cloche vit dans la barre de navigation principale (layout racine), visible depuis
tous les écrans. Le badge est calculé par `GET /api/rappels/count-actifs` (retourne
`COUNT` où `etat IN ('du', 'a_envoyer') AND lu = 0`). Le panneau se rafraîchit par
polling périodique ou à l'activation de la fenêtre (focus event).

Les trois actions du panneau sont rendues côté frontend : elles appellent respectivement
`PATCH /api/rappels/{id}/ignorer`, navigation React vers `/patients/{id}`, et
construction du lien `wa.me` avec les numéros `is_whatsapp = 1` du patient (récupérés
depuis le payload du rappel ou via `GET /api/patients/{id}`).

### D8 — Routeur FastAPI dédié

`crm/routers/rappels.py` enregistré dans `crm/server.py` via `register_all`, protégé
par le jeton de session. Routes principales :

| Méthode | Route                          | Description                          |
|---------|--------------------------------|--------------------------------------|
| POST    | `/api/rappels`                 | Créer un rappel (validation incluse) |
| GET     | `/api/rappels`                 | Lister, filtrés par état/patient     |
| GET     | `/api/rappels/count-actifs`    | Comptage badge cloche                |
| PATCH   | `/api/rappels/{id}/ignorer`    | Marquer lu (message) ou traité (alerte) |
| PATCH   | `/api/rappels/{id}/envoye`     | Marquer envoyé après `wa.me`         |
| PATCH   | `/api/rappels/{id}/traite`     | Marquer traité                       |
| PATCH   | `/api/rappels/{id}/annuler`    | Annuler un rappel planifié           |
| PUT     | `/api/rappels/{id}`            | Modifier (si état le permet)         |

## Risks / Trade-offs

- **Poste éteint à l'échéance** → N notifications au rattrapage au redémarrage. Mitigé
  par le filet de sécurité à l'ouverture de l'app (badge cloche initialisé au chargement).
- **Tâche planifiée absente/désactivée** → pas de notification de fond. Mitigé par
  l'affichage de son état dans le Paramétrage et le rafraîchissement du badge à
  l'ouverture.
- **WhatsApp assisté = clic manuel requis** → le praticien doit ouvrir WhatsApp et
  appuyer sur Envoyer. Mitigé par la notification Windows 11 et la cloche persistante.
- **Numéro WhatsApp invalide** → lien `wa.me` inopérant. Mitigé par la normalisation +
  validation à la création et avant ouverture du lien.
- **Double exécution (chevauchement de tâches)** → re-notification possible. Mitigé par
  D3 (transition atomique sur `planifie` uniquement).
- **Permissions Tauri** → ouvrir un lien externe (`wa.me`) nécessite `shell.open` dans
  `tauri.conf.json` (allowlist). À configurer au build.

## Migration Plan

1. Ajouter la table `rappels` + colonne `lu` (migration additive, bump `SCHEMA_VERSION`,
   snapshot pré-migration). Tester sur une copie de `cabinet.db` de prod (`backups/`).
2. Livrer `crm/routers/rappels.py` (API backend) + dataclass `Rappel` dans `crm/repo.py`.
3. Livrer `crm/service.py` (processus headless : traitement des rappels dus, notifications
   Windows 11, lecture settings depuis `meta`).
4. Installer/mettre à jour la tâche planifiée Windows (`schtasks`) au démarrage de l'app
   (idempotent). Documenter dans CLAUDE.md.
5. Livrer le frontend React : routeur rappels, icône cloche + badge + panneau, onglet
   Rappels sur la fiche patient, section Rappels dans le Paramétrage, bouton post-envoi
   document, lien `wa.me` avec sélecteur conditionnel.
6. Vérifier `tauri.conf.json` : `shell.open` activé pour les URLs `wa.me`.
7. Recette manuelle : création, échéance app fermée → notification + mise en file,
   rattrapage N rappels, cloche 3 actions, onglet fiche patient, annulation, envoi `wa.me`
   (1 numéro / 2 numéros), validation sur copie de DB de prod.

## Open Questions

Toutes les questions ouvertes sont désormais tranchées :

- **Intervalle tâche planifiée** → 15 min par défaut, paramétrable dans le Paramétrage
  (clé `meta` `rappels_scheduler_interval`).
- **Notifications Windows** → Windows 11 natives, activées par défaut, désactivables
  dans le Paramétrage (clé `meta` `rappels_notifs_enabled`). Mécanisme : `win32`/toast
  via pywin32 (déjà embarqué). Mode web : pas de notification de fond (filet de sécurité
  = badge cloche au chargement uniquement).
- **Récurrence des rappels** → confirmé hors v1, échéance ponctuelle uniquement.
- **Bouton d'action dans le toast** → hors v1 (impossible en mode web, best-effort
  desktop) ; l'action passe par le panneau cloche dans l'app.
- **Rattrapage après interruption** → N notifications individuelles, une par rappel échu.
- **Sélecteur de numéro** → uniquement si le patient a 2+ numéros `is_whatsapp = 1` ;
  si un seul, ouverture directe.
- **Settings headless** → table `meta` (pas `config.ini`), lus par `crm/service.py`
  directement depuis la DB.
