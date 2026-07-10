## Why

Actuellement, l'envoi de documents par WhatsApp (via Meta API ou wa.me) utilise un message standardisé unique et non personnalisable par modèle de document. Cette modification permettra aux praticiens de personnaliser le message pré-rempli envoyé via WhatsApp en fonction du modèle de document (note d'honoraires, devis, ordonnance, etc.) afin d'avoir une communication plus ciblée, et d'importer/exporter en masse cette configuration.

## What Changes

- **Personnalisation des messages WhatsApp par modèle** : Ajout d'un champ de message WhatsApp personnalisable pour chaque modèle de document (par exemple `note_honoraires`, `devis`, etc.).
- **Utilisation des variables dans les messages** : Support de variables dynamiques telles que `{{prenom}}`, `{{nom}}`, `{{document}}` dans les modèles de messages.
- **Formulaire d'édition du modèle** : Intégration de la configuration du message WhatsApp dans l'interface de paramétrage des modèles de documents.
- **Import / Export en masse** : Ajout d'une fonctionnalité d'import et d'export en masse (au format Excel `.xlsx`) des modèles de documents comprenant leurs messages WhatsApp configurés et leurs catégories, calquée sur le fonctionnement de l'import/export des actes.
- **Envoi WhatsApp intelligent** : Lors de l'ouverture d'un lien `wa.me` ou de l'envoi via Meta API pour un document donné, le message correspondant à son modèle de document est automatiquement pré-rempli en remplaçant les variables dynamiques par les données réelles du patient et du document. Si aucun message personnalisé n'est défini, le message par défaut est utilisé en repli.

## Capabilities

### New Capabilities
- `whatsapp-document-templates`: Gestion des messages WhatsApp personnalisés par modèle de document, y compris l'envoi dynamique avec variables et l'import/export en masse des modèles et messages au format Excel.

### Modified Capabilities

## Impact

- **Base de données** : Version du schéma augmentée (v15). Ajout de la colonne `whatsapp_message` TEXT dans la table `template_meta`.
- **API Backend (FastAPI)** :
  - Mise à jour des schémas Pydantic liés aux modèles pour inclure `whatsapp_message`.
  - Modification des routes GET et PUT de configuration de catégorie/modèle pour intégrer le message.
  - Nouvelles routes pour l'export (`GET /api/templates/export`) et l'import (`POST /api/templates/import`) des modèles.
  - Mise à jour du client et des générateurs WhatsApp si nécessaire pour utiliser le texte dynamique.
- **Frontend (React)** :
  - Mise à jour de la table et des formulaires de `ModelesTab.tsx` pour configurer le message WhatsApp par modèle.
  - Ajout des boutons Importer / Exporter dans l'onglet des modèles avec boîte de dialogue de rapport d'importation.
  - Remplacement de la génération de texte statique dans `DocumentsTab.tsx` (action `open-wa-me`) par le message dynamique pré-rempli.
