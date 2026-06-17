## Context

Le CRM génère des notes d'honoraires dans `output/` (PDF ou JPG) puis les envoie
par email via Mailjet. L'envoi email est porté par `src/mailer.py`
(`MailjetClient`), orchestré par `crm/generator.send_document(conn, document,
config, template_id)`, et le statut est suivi dans la table `documents`
(`mailjet_message_id`, `mailjet_status`, `date_refresh_status`, …). L'interface
Flet (`crm/app.py`, fichier unique) affiche un bouton d'envoi email sur chaque
ligne de document (`_doc_row` ~L1847 et `_doc_line_row` ~L2809) via le dialogue
`_send_dialog` (~L3960), exécuté en arrière-plan par `_run_busy`.

L'objectif est d'ajouter un **canal d'envoi WhatsApp** parallèle, reposant sur
l'**API officielle Meta WhatsApp Cloud**, en réutilisant ce moteur sans le
modifier — comme l'impression (`crm/printing.py`) qui s'exécute déjà côté
serveur, identiquement en mode desktop et web.

Contraintes structurantes (CLAUDE.md) : Windows uniquement ; `src/` reste
indépendant de l'UI ; schéma SQLite **additif/expand-only** avec bump de
`SCHEMA_VERSION`, migration idempotente et snapshot pré-migration ; le token
Meta est un **secret** (hors versionnement, jamais journalisé).

Pré-requis externes côté cabinet : compte Meta Business, numéro WhatsApp
Business vérifié, et **modèle(s) de message approuvé(s)** par Meta — Meta
n'autorise l'envoi avec pièce jointe en initiation de conversation que via un
template approuvé.

## Goals / Non-Goals

**Goals:**
- Envoyer un document déjà généré vers le WhatsApp du patient, **pièce jointe
  incluse, sans manipulation manuelle**.
- Réutiliser le fichier `output/` existant et le pattern d'orchestration
  (`generator` → `_run_busy` → mise à jour `documents`).
- Suivre un **statut WhatsApp indépendant** du statut email, rafraîchissable.
- Configuration des identifiants Meta dans Paramétrage › WhatsApp, sans toucher
  au flux email.
- Fonctionner à l'identique en desktop et en web (exécution serveur).

**Non-Goals:**
- Pas de remplacement de l'email Mailjet (canal additionnel).
- Pas de réception/lecture des réponses WhatsApp ni de conversation bidirectionnelle.
- Pas d'abstraction multi-fournisseurs : on implémente **Meta Cloud API**
  uniquement (Twilio/360dialog hors périmètre).
- Pas de gestion de la création/approbation des modèles Meta (faite côté Meta
  Business Manager par le cabinet) ; l'app ne fait que référencer un modèle existant.
- Pas de webhook entrant (le statut est obtenu par interrogation, comme Mailjet).

## Decisions

### D1 — Nouveau module `src/whatsapp.py`, calqué sur `src/mailer.py`
Créer un `WhatsAppClient` indépendant de l'UI, avec trois opérations sur l'API
Meta Graph (`https://graph.facebook.com/<version>`) :
1. `upload_media(path)` → POST `/<phone_number_id>/media` (multipart) ⇒ `media_id`.
2. `send_document(to_e164, media_id, filename, template, lang, variables)` →
   POST `/<phone_number_id>/messages` ⇒ `message_id`.
3. `get_status(message_id)` → lecture du statut de remise.

*Rationale* : respecte la règle « `src/` indépendant de l'UI » et le précédent
`MailjetClient`. Auth par `Bearer <access_token>`. HTTP via `requests` (déjà
présent), aucune nouvelle dépendance lourde.

*Alternative écartée* : appeler l'API directement depuis `crm/generator.py` —
rejeté pour garder la logique réseau/secret isolée et testable comme Mailjet.

### D2 — Pièce jointe via upload `/media` (media_id), pas par URL publique
Meta accepte un document soit par URL publique, soit par `media_id` issu d'un
upload préalable. L'app est locale/desktop sans serveur HTTP public → on
**uploade le fichier** pour obtenir un `media_id` puis on l'attache.

*Rationale* : c'est la seule voie fiable sans héberger les notes sur une URL
exposée (et c'est précisément ce qui rendait Twilio inadapté ici).

### D3 — Persistance : migration additive sur `documents`
Ajouter 4 colonnes nullable : `whatsapp_message_id TEXT`, `whatsapp_status
TEXT`, `whatsapp_date_envoi TEXT`, `whatsapp_date_refresh TEXT`. Bump
`SCHEMA_VERSION` (7 → 8) et ajouter une étape `_migrate()` idempotente gardée par
`_column_exists`. Étendre le dataclass `Document` (`crm/repo.py`) et le CRUD.

*Rationale* : statut email et WhatsApp doivent coexister sur un même document
(D5). Colonnes nullable ⇒ conforme expand-only, zéro perte sur base existante.

*Alternative écartée* : table `envois` séparée (un canal = une ligne) — plus
propre à terme mais surdimensionné pour 2 canaux ; reporté si d'autres canaux
arrivent.

### D4 — Réglages dans `meta` via `repo.get_setting`/`set_setting` (pas de migration)
Clés : `whatsapp_phone_number_id`, `whatsapp_access_token`,
`whatsapp_template_lang`. Nouvel onglet dans `_param_submenu` (« WhatsApp ») +
carte `_whatsapp_settings_card`, calquée sur `_printer_settings_card`.

L'**indicatif pays par défaut (+216, paramétrable)** n'est **pas** redéfini ici :
on réutilise le réglage partagé déjà introduit par le change
`rappels-automatiques` (config.ini / Paramétrage), pour éviter un doublon de
configuration entre les deux canaux WhatsApp.

*Rationale* : même mécanisme que l'imprimante (`PRINTER_KEY`), aucune migration.
Le token reste hors `git` (table `meta` de `cabinet.db`, non versionnée) et
n'est jamais réaffiché en clair ni journalisé (exigence secret).

### D8 — Un modèle Meta par type de document (réutilisation possible)
Le nom du modèle Meta n'est pas un réglage global unique : c'est une
**correspondance « type de document → nom de modèle Meta »**. Plusieurs types
peuvent pointer vers le **même** modèle (réutilisation explicite). À l'envoi, le
système choisit le modèle d'après `document.type` ; à défaut de correspondance,
il refuse l'envoi en renvoyant vers Paramétrage › WhatsApp.

Stockage : une clé `meta` par type (ex. `whatsapp_template:<type>`) ou un JSON
unique `whatsapp_templates` (mapping type → modèle). Décision : **JSON unique**
`whatsapp_templates`, plus simple à éditer dans une seule carte de réglages.

*Rationale* : aligne le WhatsApp sur la logique des modèles d'email (un modèle
adaptable par type) tout en autorisant un modèle générique partagé.

### D9 — Variables injectées dans le modèle Meta : nom, prénom, type de document
Les variables passées au template Meta sont limitées à **prénom, nom, type de
document**. Pas de montant ni d'autre donnée sensible dans le corps WhatsApp
(le détail chiffré reste dans la pièce jointe). L'ordre/position des variables
suit la définition du modèle approuvé côté Meta (placeholders `{{1}}`, `{{2}}`,
`{{3}}`).

*Rationale* : message court, lisible, non sensible ; le document joint porte le
détail.

*Alternative* : mettre les clés dans `config.ini` (comme Mailjet). Possible
aussi, mais `meta` évite d'éditer un fichier à la main et reste cohérent avec le
réglage imprimante. Décision : `meta`.

### D5 — Statuts indépendants + nouveaux libellés UI
Le statut email (`statut`/`mailjet_status`) n'est pas réutilisé pour WhatsApp.
Le suivi WhatsApp vit dans ses propres colonnes (D3). Ajouter des libellés
dédiés (ex. « WhatsApp envoyé », « WhatsApp lu », « WhatsApp erreur ») dans les
maps de `crm/app.py`. Boutons WhatsApp ajoutés dans `_doc_row`/`_doc_line_row`,
visibles si `patient.telephone` est renseigné et le fichier généré.

*Rationale* : un document peut légitimement être envoyé par un canal et pas
l'autre ; mélanger les statuts perdrait de l'information.

### D6 — Orchestration : `generator.send_document_whatsapp(...)` + `_run_busy`
Nouvelle fonction parallèle à `send_document` : vérifie fichier + téléphone +
config, normalise le numéro (D7), résout le modèle Meta d'après `document.type`
(D8), appelle `WhatsAppClient` (upload → envoi), écrit les colonnes WhatsApp,
journalise (log dédié type `logs/whatsapp.log`), `repo.log_audit`. Le modèle
étant déterminé par le type de document, l'envoi est direct (confirmation
simple) ; `_run_busy` (thread d'arrière-plan, anti double-clic) exactement comme
l'email. `refresh_whatsapp_status(...)` pour le rafraîchissement.

### D7 — Normalisation E.164
Helper de normalisation : nettoyage des séparateurs, gestion du `00`/`+`,
application de l'**indicatif pays par défaut partagé** (+216, paramétrable —
réglage commun avec `rappels-automatiques`, cf. D4) si numéro local. Refus
explicite si le résultat n'est pas plausible, plutôt qu'un appel API voué à
l'échec.

*Rationale* : les numéros patients sont saisis librement (`telephone` TEXT) ;
l'API Meta exige du E.164. Implémentation maison légère suffisante ; `phonenumbers`
envisageable mais non retenu pour éviter une dépendance supplémentaire.

## Risks / Trade-offs

- **Fenêtre de 24 h / modèles obligatoires** → En initiation, Meta impose un
  message *template* approuvé ; on documente clairement le pré-requis et on
  guide l'utilisateur (message d'erreur explicite + renvoi vers Paramétrage)
  quand le modèle manque ou n'est pas approuvé.
- **Numéros patients hétérogènes/invalides** → Normalisation E.164 + préfixe
  pays par défaut + refus propre avec invitation à corriger la fiche patient,
  jamais d'appel API silencieusement erroné.
- **Fuite du token Meta** → Stocké dans `meta` (hors git), masqué à l'affichage,
  jamais journalisé ; mêmes égards que les clés Mailjet.
- **Coût par conversation Meta** → Hors logiciel ; le bouton est une action
  explicite par document (pas d'envoi de masse automatique non sollicité).
- **Dérive de version de l'API Graph** → Version d'API centralisée dans
  `src/whatsapp.py` (constante unique) pour un bump localisé.
- **Quota/erreurs transitoires** → Statut « erreur » + message conservé +
  possibilité de relancer (l'action reste rejouable, idempotence par fichier
  inchangée côté génération).

## Migration Plan

1. **Expand** : ajouter les colonnes WhatsApp nullable à `documents` ; bump
   `SCHEMA_VERSION` 7 → 8 ; étape `_migrate()` idempotente gardée par
   `_column_exists`. **Snapshot pré-migration** de `cabinet.db` avant `connect()`
   (copie labellisée `cabinet-pre-v8-*.db`, exemptée du prune `KEEP=10`).
2. **Code** : `src/whatsapp.py`, fonctions `generator.send_document_whatsapp` /
   `refresh_whatsapp_status` + helper E.164 ; dataclass `Document` + CRUD étendus.
3. **UI** : boutons WhatsApp, dialogue d'envoi, libellés de statut, onglet
   Paramétrage › WhatsApp.
4. **Validation** sur une copie de `cabinet.db` issue de `backups/` : documents
   et statuts email existants intacts ; envoi WhatsApp réel vers un numéro de
   test ; rafraîchissement de statut.
5. **Rollback** : la fonctionnalité est additive — désactiver/masquer le bouton
   suffit ; les colonnes nullables restent inertes. Anti-downgrade déjà assuré
   par le refus d'ouvrir une base `schema_version` plus récente que l'app.

## Décisions arrêtées (questions précédemment ouvertes)

- **Modèles Meta** : **un modèle par type de document**, avec possibilité de
  faire pointer plusieurs types vers le **même** modèle (mapping type → modèle,
  cf. D8).
- **Variables du message** : **prénom, nom, type de document** uniquement (D9).
  Pas de montant dans le corps WhatsApp ; le détail reste dans la pièce jointe.
- **Indicatif pays par défaut** : **+216 (Tunisie), paramétrable**, via le
  **réglage partagé** déjà introduit par `rappels-automatiques` (pas de doublon).

## Pré-requis & configuration côté Meta (à réaliser par le cabinet)

Ces étapes se font **hors application**, dans les outils Meta. Elles sont
indispensables avant qu'un envoi puisse fonctionner. À reporter dans la doc
utilisateur du cabinet.

1. **Compte Meta Business** — créer/identifier un compte sur
   business.facebook.com (Business Manager).
2. **Application Meta + produit WhatsApp** — sur developers.facebook.com, créer
   une app de type *Business*, puis y ajouter le produit **WhatsApp**.
3. **Numéro WhatsApp Business** — enregistrer et **vérifier** un numéro de
   téléphone dédié (non déjà utilisé sur un compte WhatsApp classique). Récupérer
   son **Phone Number ID** (identifiant numérique, ≠ le numéro affiché).
4. **WhatsApp Business Account ID (WABA ID)** — noté dans la console ; utile pour
   la gestion des modèles.
5. **Token d'accès** — générer un **token d'accès permanent** (via un *System
   User* du Business Manager avec les permissions `whatsapp_business_messaging`
   et `whatsapp_business_management`). Éviter le token temporaire de test (expire
   en 24 h). **C'est un secret** : il sera saisi dans Paramétrage › WhatsApp, pas
   committé.
6. **Modèle(s) de message approuvé(s)** — dans WhatsApp Manager › *Message
   Templates*, créer au moins un modèle de catégorie **Utility**, avec :
   - une **langue** (ex. `fr`),
   - un **corps** contenant les variables dans l'ordre **{{1}} = prénom,
     {{2}} = nom, {{3}} = type de document**,
   - un **en-tête de type Document** (pour autoriser la pièce jointe PDF/JPG).
   Le modèle doit être **soumis et approuvé par Meta** (peut prendre quelques
   minutes à 24 h). Un même modèle peut servir à plusieurs types de documents.
7. **Limites & facturation** — vérifier le palier de qualité/volume du numéro et
   activer un moyen de paiement Meta (facturation par conversation).

**À renseigner ensuite dans l'app (Paramétrage › WhatsApp) :**

| Réglage | Source Meta | Clé `meta` |
| --- | --- | --- |
| Phone Number ID | étape 3 | `whatsapp_phone_number_id` |
| Token d'accès permanent | étape 5 | `whatsapp_access_token` (secret, masqué) |
| Langue du modèle | étape 6 | `whatsapp_template_lang` |
| Modèle par type de document | étape 6 | `whatsapp_templates` (JSON type→modèle) |
| Indicatif pays par défaut | — | réglage **partagé** `rappels-automatiques` |

## Open Questions

- **Catégorie/en-tête exact du modèle** : confirmer que le cabinet crée bien un
  modèle *Utility* avec en-tête **Document** (sinon la pièce jointe est refusée).
- **Plusieurs numéros/WABA** : on suppose un seul numéro émetteur ; multi-numéro
  hors périmètre.
