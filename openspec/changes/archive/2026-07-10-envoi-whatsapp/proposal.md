## Why

Aujourd'hui, une note d'honoraires générée ne peut être transmise au patient
que par email (Mailjet). Or beaucoup de patients du cabinet ne consultent pas
leur boîte mail mais répondent immédiatement sur WhatsApp. Permettre l'envoi
direct du document vers le WhatsApp du patient — pièce jointe comprise, sans
ressaisie ni manipulation manuelle — accélère la transmission, réduit les
relances et s'aligne sur le canal réellement utilisé par les patients.

## What Changes

- Ajout d'un **second canal d'envoi** d'un document généré : **WhatsApp**, en
  parallèle de l'email existant (l'email n'est pas remplacé).
- Intégration de l'**API officielle Meta WhatsApp Cloud** : le PDF/JPG déjà
  généré dans `output/` est **uploadé puis joint automatiquement** au message
  WhatsApp envoyé au numéro du patient (aucune pièce jointe manuelle). Le message
  injecte **prénom, nom et type de document** (aucun montant dans le corps).
- Nouveau **bouton « Envoyer par WhatsApp »** sur chaque ligne de document
  (vue fiche patient et page Documents), affiché quand le patient a un
  **téléphone** renseigné et que le document est généré.
- **Suivi de statut WhatsApp** par document (envoyé / remis / lu / échec),
  stocké en base et rafraîchissable comme le statut Mailjet.
- Nouvel onglet **Paramétrage › WhatsApp** pour saisir les identifiants Meta
  (Phone Number ID, token d'accès, langue du modèle) et la **correspondance
  « type de document → modèle Meta »** (un modèle par type, réutilisable entre
  types).
- **Normalisation du numéro de téléphone** au format international E.164 via
  l'**indicatif pays par défaut partagé** (+216, paramétrable) déjà introduit par
  la fonctionnalité de rappels — pas de doublon de réglage.
- L'envoi s'exécute **côté serveur** (machine où tourne l'app), donc identique
  en mode desktop et en mode web — comme l'impression.

## Capabilities

### New Capabilities
- `envoi-whatsapp`: envoi d'un document généré vers le WhatsApp du patient via
  l'API Meta WhatsApp Cloud (upload + pièce jointe + message), configuration des
  identifiants Meta, normalisation du numéro, et suivi du statut de remise/lecture.

### Modified Capabilities
<!-- Aucune capability existante (openspec/specs/ est vide). L'email Mailjet
     reste inchangé : WhatsApp est un canal additionnel, pas une modification
     du comportement d'envoi email. -->

## Impact

- **Code**
  - `src/` : nouveau module `src/whatsapp.py` (`WhatsAppClient` — analogue à
    `MailjetClient` : upload média + envoi message + lecture de statut), réutilisé
    sans modifier le moteur existant.
  - `crm/generator.py` : nouvelle fonction `send_document_whatsapp(...)` (parallèle
    à `send_document`) + `refresh_whatsapp_status(...)` ; aide de normalisation E.164.
  - `crm/db.py` : **migration additive** (bump `SCHEMA_VERSION`) — nouvelles
    colonnes nullable sur `documents` (`whatsapp_message_id`, `whatsapp_status`,
    `whatsapp_date_envoi`, `whatsapp_date_refresh`). Aucune suppression/renommage
    (règle expand-only, snapshot pré-migration).
  - `crm/repo.py` : champs ajoutés au dataclass `Document` + mises à jour CRUD.
  - `crm/app.py` : bouton WhatsApp dans `_doc_row` / `_doc_line_row`, dialogue
    d'envoi, libellés de statut, onglet Paramétrage › WhatsApp (clés via
    `repo.get_setting`/`set_setting`, sans migration).
- **Dépendances** : aucune nouvelle lib lourde — appels HTTP via `requests`
  (déjà utilisé par Mailjet) vers l'API Meta Graph.
- **Configuration** : nouveaux réglages WhatsApp. Le token d'accès Meta est un
  **secret** — stocké hors versionnement (meta/`config.ini`, jamais committé),
  traité comme les clés Mailjet.
- **Pré-requis externes (à la charge du cabinet)** : compte Meta Business,
  numéro WhatsApp Business vérifié, et **modèle(s) de message approuvé(s)** par
  Meta (obligatoire pour initier une conversation avec pièce jointe).
- **Coût** : facturation Meta par conversation (hors périmètre logiciel).
- **Données** : un document peut désormais porter deux statuts d'envoi
  indépendants (email et WhatsApp) ; aucune donnée existante n'est perdue ni
  réinterprétée (les notes déjà générées restent reconnues à l'identique).
