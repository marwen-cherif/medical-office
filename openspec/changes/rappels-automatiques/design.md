## Context

Le CRM (`crm/`, Flet desktop + web, SQLite `data/cabinet.db`) génère et envoie des
documents (notes d'honoraires, etc.) via le moteur partagé `src/` (Word COM, Mailjet,
PyMuPDF). L'application n'est **pas allumée en permanence** : c'est un outil de bureau
ouvert ponctuellement. Aujourd'hui aucun suivi temporel n'est possible après l'envoi
d'un document.

Le besoin métier : au moment d'envoyer un document (ou à tout moment), planifier soit une
**alerte interne** pour le praticien, soit un **message WhatsApp au patient** à une date
future (ex. rappel de contrôle à +2 mois), rédigé à l'avance, avec une notification
fiable à l'échéance même application fermée.

Contraintes structurantes connues :
- **Préservation des données (CLAUDE.md)** : schéma additif/expand-only, bump
  `SCHEMA_VERSION` + `_migrate()` idempotente guardée par `_column_exists`, snapshot
  pré-migration, anti-downgrade. La DB de prod est toujours existante et peuplée.
- **WhatsApp** : l'API officielle (Meta Cloud / Twilio) n'offre pas de planification
  longue (Twilio plafonne `SendAt` à 7 jours) et **interdit le texte libre hors fenêtre
  de 24 h** — seuls des modèles pré-approuvés (petites variables) sont permis. Un envoi
  WhatsApp automatique à +2 mois avec texte libre rédigé par le praticien est donc
  **impossible** par l'API officielle. Le seul moyen d'autoriser un **texte libre**
  rédigé à l'avance est l'envoi **assisté** (ouverture de WhatsApp pré-rempli, clic
  manuel).
- **Décision produit** : pas d'email / Mailjet pour les messages patients ; canal patient
  = **WhatsApp assisté uniquement**.

## Goals / Non-Goals

**Goals:**

- Stocker des rappels datés (alerte interne ou message patient WhatsApp) rattachables à un
  patient/document, dans SQLite, de façon additive et sûre pour la prod.
- Déclencher/notifier les rappels échus **même application fermée**, via une tâche
  planifiée Windows exécutant un mode « service » sans interface.
- À l'échéance, mettre les messages patients en **file WhatsApp** et permettre leur envoi
  **en un clic** (texte libre pré-rempli via `wa.me`).
- Présenter au démarrage les rappels dus (alertes internes, file WhatsApp).
- Permettre la création d'un rappel pré-rempli juste après l'envoi d'un document.

**Non-Goals:**

- **Aucun email / Mailjet** dans cette fonctionnalité.
- Pas d'envoi WhatsApp 100 % automatique en texte libre (impossible, cf. contrainte
  Meta). L'intégration WhatsApp Cloud API par modèles approuvés est documentée comme
  **évolution future**, hors de cette version.
- Pas de SMS ni d'autres canaux.
- Pas de récurrence complexe (rappels répétitifs) en v1 — uniquement une échéance
  ponctuelle par rappel.
- Pas de modification du moteur `src/`.

## Decisions

### D1 — Une table `rappels` unique, polymorphe par `type`

Une seule table couvre les deux types. Colonnes principales :
`id`, `type` (`alerte_interne` | `message_patient`), `patient_id` (nullable),
`document_id` (nullable), `titre`, `message` (texte libre, destiné au patient pour un
`message_patient`), `echeance` (date/heure ISO), `etat`, `created_at`, `notified_at`
(nullable), `sent_at` (nullable).

États (`etat`) :
- `planifie` → à l'échéance : `du` (alerte interne) ou `a_envoyer` (message patient mis en
  file WhatsApp) → `traite` (alerte traitée) ou `envoye` (WhatsApp envoyé en un clic).
- `annule` : annulation manuelle avant échéance.

*Alternative écartée* : deux tables séparées. Rejetée car les deux partagent échéance,
rattachements, cycle de vie et la requête « rappels dus » ; une table simplifie la file et
l'UI.

### D2 — Déclenchement par tâche planifiée Windows appelant un mode « service »

Un point d'entrée headless (ex. `Cabinet-CRM.exe --service` / `python -m crm.service`)
ouvre la DB, lit les rappels dus (`etat=planifie` et `echeance<=maintenant`), fait passer
chacun à `du`/`a_envoyer`, émet une **notification Windows** et sort. Une **tâche
planifiée Windows** (créée via `schtasks`) l'exécute à intervalle régulier (ex. 15–30 min).

Le mode service **n'envoie pas** le message au patient : le canal WhatsApp assisté exige
un clic du praticien. Son rôle est de **notifier** à temps (même app fermée) et de
**mettre en file**. Il ne dépend ni de Flet ni de Word ni de Mailjet ; il réutilise
`crm/db.py` (`connect()`), `crm/repo.py` et un envoi de notification Windows
(`win32`/toast, déjà disponible via pywin32 embarqué).

*Pourquoi pas un service Windows permanent (SCM)* : surdimensionné pour un poste de
cabinet ; une tâche planifiée à intervalle court suffit, latence ≤ intervalle acceptable à
l'échelle du mois. *Pourquoi pas seulement « à l'ouverture de l'app »* : l'utilisateur
veut être notifié à l'échéance sans avoir à ouvrir l'app.

### D3 — Idempotence par état + transition atomique

Le service ne traite que les rappels `planifie` dont l'échéance est dépassée, et
horodate `notified_at` lors du passage à `du`/`a_envoyer` en une transaction. Un rappel
déjà `du`/`a_envoyer`/`envoye`/`traite`/`annule` est ignoré : pas de re-notification en
boucle, pas de doublon en file, même si la tâche se chevauche ou rejoue.

### D4 — Canal patient : WhatsApp assisté via `wa.me`, jamais automatique

Flux confirmé : à l'échéance, le service de fond fait passer le `message_patient` à
`a_envoyer` (file) et émet une **notification Windows** (« Rappel à envoyer : patient X »).
Le praticien ouvre l'app (un clic sur le toast peut la mettre au premier plan) ; dans la
file « Rappels dus », l'action **« Envoyer via WhatsApp »** ouvre
`https://wa.me/<numero>?text=<message_urlencodé>` (WhatsApp Web/Desktop) avec le bon
contact et le texte pré-rempli ; le praticien appuie sur *Envoyer* dans WhatsApp, puis
marque le rappel `envoye`. Le numéro est normalisé au format international (indicatif par
défaut **+216**, paramétrable) à partir du téléphone patient ; un numéro non normalisable
bloque l'action avec un message clair. En mode web, le lien s'ouvre dans le navigateur du
praticien.

Le bouton « un clic » vit **dans l'app**, pas dans la bulle de notification : un toast ne
fait qu'alerter, l'action d'ouverture de `wa.me` passe par l'écran de file. Un bouton
d'action intégré au toast desktop est envisagé comme amélioration best-effort (cf. Open
Questions), impossible en mode web.

*Pourquoi assisté* : seul moyen d'autoriser le **texte libre** rédigé à l'avance ; la voie
automatique imposerait des modèles Meta approuvés (hors v1).

### D5 — Migration additive + snapshot pré-migration

`CREATE TABLE IF NOT EXISTS rappels (...)`, bump `SCHEMA_VERSION`, étape `_migrate()`
idempotente. Conformément à CLAUDE.md, un snapshot pré-migration labellisé
(`cabinet-pre-v<N>-…db`) est pris **avant** la migration et exempté du prune `KEEP=10`.
Aucune colonne/table existante n'est modifiée.

## Risks / Trade-offs

- **Le poste est éteint à l'échéance** → la tâche planifiée ne s'exécute pas à l'heure
  pile. Mitigation : au prochain démarrage du poste/tâche, tous les rappels dont
  `echeance<=maintenant` sont notifiés/mis en file (rattrapage) ; aucun rappel perdu, juste
  retardé.
- **Tâche planifiée absente/désactivée** → pas de notification de fond. Mitigation : l'app
  vérifie aussi les rappels dus à chaque ouverture (présentation au démarrage) ; afficher
  l'état de la tâche planifiée dans Paramétrage.
- **WhatsApp assisté = pas vraiment automatique** → dépend d'un clic du praticien.
  Mitigation : clairement présenté comme tel ; la notification garantit qu'il y pense à
  temps.
- **Numéro WhatsApp invalide/au mauvais format** → lien `wa.me` inopérant. Mitigation :
  normalisation + validation à la création du rappel et avant ouverture du lien, message
  d'erreur explicite.
- **Double exécution (chevauchement de tâches)** → re-notification. Mitigation : D3
  (transition d'état atomique, traitement du seul état `planifie`).

## Migration Plan

1. Ajouter la table `rappels` (migration additive, bump `SCHEMA_VERSION`, snapshot
   pré-migration). Tester sur une copie de `cabinet.db` de prod (`backups/`).
2. Livrer le mode service headless (notification + mise en file) et le câblage UI
   (création, liste, file WhatsApp, présentation au démarrage, envoi `wa.me` en un clic).
3. À la première exécution post-maj, installer/mettre à jour la tâche planifiée Windows
   (`schtasks`) ; documenter l'opération et le paramétrage (intervalle, activation).
4. **Rollback** : la fonctionnalité est additive. Revenir à l'exe précédent fonctionne
   (anti-downgrade selon la règle) ; la table `rappels` inutilisée reste inerte.
   Désinstaller la tâche planifiée si on retire la fonctionnalité.

## Open Questions

- Intervalle par défaut de la tâche planifiée (15 vs 30 min) et exposition dans
  `config.ini` / Paramétrage ?
- Mécanisme de notification Windows en mode service (toast `win10toast`/`win32` vs
  message simple) et comportement en mode web (notification serveur vs uniquement à
  l'ouverture) ?
- Récurrence des rappels (répéter tous les N mois) : confirmer que c'est hors v1.
- Bouton d'action directement dans le toast Windows (ouverture `wa.me` sans ouvrir
  l'écran de l'app) : amélioration best-effort desktop uniquement (impossible en web) ;
  le bouton dans la file de l'app reste la méthode garantie.

**Décisions tranchées :**
- Normalisation des numéros : **indicatif pays par défaut +216 (Tunisie), paramétrable**
  dans `config.ini` / Paramétrage, appliqué aux numéros locaux saisis sans préfixe
  international.
