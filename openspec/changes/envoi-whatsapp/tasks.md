## 1. Base de données (migration additive)

- [ ] 1.1 Ajouter les colonnes nullable `whatsapp_message_id`, `whatsapp_status`, `whatsapp_date_envoi`, `whatsapp_date_refresh` à la table `documents` (`crm/db.py`)
- [ ] 1.2 Bumper `SCHEMA_VERSION` 7 → 8 et ajouter une étape `_migrate()` idempotente gardée par `_column_exists`
- [ ] 1.3 Garantir le snapshot pré-migration `cabinet-pre-v8-*.db` avant `connect()`, exempté du prune `KEEP=10`
- [ ] 1.4 Tester la migration sur une copie de `cabinet.db` issue de `backups/` (documents + statuts email existants intacts)

## 2. Modèle de données (repo)

- [ ] 2.1 Étendre le dataclass `Document` (`crm/repo.py`) avec les 4 champs WhatsApp
- [ ] 2.2 Mettre à jour les requêtes CRUD (`insert`/`update`/`select` documents) pour lire/écrire ces champs

## 3. Client API Meta WhatsApp Cloud (`src/whatsapp.py`)

- [ ] 3.1 Créer `src/whatsapp.py` avec `WhatsAppClient` (auth Bearer, version d'API Graph centralisée en constante), indépendant de l'UI
- [ ] 3.2 Implémenter `upload_media(path)` → `media_id` (POST `/<phone_number_id>/media`, multipart)
- [ ] 3.3 Implémenter `send_document(to_e164, media_id, filename, template, lang, variables)` → `message_id` (POST `/messages`)
- [ ] 3.4 Implémenter `get_status(message_id)` (lecture du statut de remise) + classe d'erreur dédiée (type `WhatsAppError`)
- [ ] 3.5 Ajouter une journalisation dédiée (`logs/whatsapp.log`) sans jamais journaliser le token

## 4. Normalisation du numéro (E.164)

- [ ] 4.1 Écrire un helper de normalisation E.164 (nettoyage séparateurs, gestion `00`/`+`, préfixe pays par défaut)
- [ ] 4.2 Refuser proprement un numéro inexploitable (message clair, pas d'appel API)

## 5. Orchestration (generator)

- [ ] 5.1 Implémenter `generator.send_document_whatsapp(conn, document, patient, settings)` : vérifs fichier + téléphone + config, résolution du modèle Meta d'après `document.type` (refus si absent), normalisation (§4), variables {prénom, nom, type}, upload + envoi, écriture des colonnes WhatsApp + `repo.log_audit`
- [ ] 5.2 Gérer les échecs : statut `erreur` + message conservé, sans interrompre l'application
- [ ] 5.3 Implémenter `generator.refresh_whatsapp_status(conn, document, settings)` (parallèle à `refresh_mail_status`)

## 6. Paramétrage › WhatsApp (UI réglages)

- [ ] 6.1 Définir les clés de réglage (`whatsapp_phone_number_id`, `whatsapp_access_token`, `whatsapp_template_lang`, `whatsapp_templates` JSON type→modèle) lues/écrites via `repo.get_setting`/`set_setting`
- [ ] 6.2 Réutiliser l'indicatif pays par défaut **partagé** de `rappels-automatiques` (ne PAS créer de clé `whatsapp_default_country` en doublon)
- [ ] 6.3 Ajouter l'onglet « WhatsApp » dans `_param_submenu` et la carte `_whatsapp_settings_card` (calquée sur `_printer_settings_card`), avec l'éditeur de correspondance type de document → modèle Meta
- [ ] 6.4 Masquer le token après enregistrement (champ masqué / indication « configuré » sans révéler la valeur)

## 7. Boutons & dialogue d'envoi (UI documents)

- [ ] 7.1 Ajouter le bouton « Envoyer par WhatsApp » dans `_doc_row` et `_doc_line_row`, visible si `patient.telephone` renseigné et document généré (coexistant avec l'email)
- [ ] 7.2 Créer le dialogue `_send_whatsapp_dialog` (choix du modèle si plusieurs) exécuté via `_run_busy` (thread d'arrière-plan)
- [ ] 7.3 Ajouter les libellés de statut WhatsApp dédiés (envoyé / remis / lu / erreur) dans les maps de `crm/app.py`
- [ ] 7.4 Ajouter l'action de rafraîchissement du statut WhatsApp sur la ligne du document
- [ ] 7.5 Bloquer l'envoi avec message explicite + renvoi vers Paramétrage › WhatsApp si identifiants incomplets

## 8. Validation manuelle (Windows + Word)

- [ ] 8.1 Envoi WhatsApp réel d'un document vers un numéro de test (pièce jointe reçue)
- [ ] 8.2 Vérifier l'indépendance des statuts email et WhatsApp sur un même document
- [ ] 8.3 Vérifier le rafraîchissement du statut (remis/lu) et l'affichage du libellé
- [ ] 8.4 Vérifier les cas d'erreur : token invalide, modèle manquant, numéro inexploitable, fichier introuvable
- [ ] 8.5 Vérifier le comportement identique en mode desktop et en mode web (`CRM_WEB=1`)

## 9. Documentation de configuration Meta (côté cabinet)

- [ ] 9.1 Rédiger la doc pas-à-pas de configuration Meta (compte Business, app + produit WhatsApp, numéro vérifié + Phone Number ID, WABA ID, token permanent via System User) — cf. design.md « Pré-requis & configuration côté Meta »
- [ ] 9.2 Documenter la création d'un modèle approuvé (catégorie Utility, langue, en-tête Document pour la pièce jointe, variables {{1}} prénom / {{2}} nom / {{3}} type)
- [ ] 9.3 Documenter le mapping des valeurs Meta vers les champs de Paramétrage › WhatsApp (tableau de correspondance)
