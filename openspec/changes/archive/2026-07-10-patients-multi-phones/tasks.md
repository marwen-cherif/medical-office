## 1. Base de données et Modèle de Données

- [x] 1.1 Augmenter `SCHEMA_VERSION` à 15 dans `apps/api/crm/db.py`
- [x] 1.2 Ajouter la définition de la table `patient_phones` dans la variable `_SCHEMA` de `apps/api/crm/db.py`
- [x] 1.3 Implémenter la migration v15 dans la méthode `_migrate()` de `apps/api/crm/db.py` pour ajouter la table et effectuer le backfill automatique des numéros existants de `patients.telephone` (avec la relation "Lui-même" et `is_whatsapp = 1`)
- [x] 1.4 Définir la dataclass `PatientPhone` dans `apps/api/crm/repo.py`
- [x] 1.5 Modifier la dataclass `Patient` pour y inclure `telephones: list[PatientPhone]`
- [x] 1.6 Implémenter dans `apps/api/crm/repo.py` les fonctions utilitaires pour gérer les téléphones : lecture de la liste des téléphones d'un patient et synchronisation lors de la création/mise à jour du patient (avec mise à jour de la colonne `patients.telephone` avec le numéro principal)

## 2. API Backend et Contrôleurs

- [x] 2.1 Définir les modèles Pydantic `PatientPhoneIn` et `PatientPhoneOut` dans `apps/api/crm/routers/patients.py`
- [x] 2.2 Mettre à jour `PatientIn` et `PatientOut` dans `apps/api/crm/routers/patients.py` pour supporter la liste `telephones`
- [x] 2.3 Mettre à jour les routeurs de création, mise à jour et obtention de patient dans `apps/api/crm/routers/patients.py` pour persister et restituer les téléphones
- [x] 2.4 Mettre à jour la méthode `send_document_whatsapp` de `apps/api/crm/generator.py` pour accepter un paramètre optionnel `target_phone`
- [x] 2.5 Modifier le schéma d'entrée et la route `POST /documents/{document_id}/send-whatsapp` dans `apps/api/crm/routers/documents.py` pour accepter optionnellement le numéro cible dans le corps de la requête

## 3. Frontend - Saisie et Édition du Patient

- [x] 3.1 Créer un helper de pays avec les indicatifs téléphoniques internationaux et les émojis de drapeaux dans le frontend
- [x] 3.2 Implémenter une fonction d'analyse et de découpage des numéros E.164 (pour séparer indicatif et numéro local) dans le formulaire patient
- [x] 3.3 Mettre à jour le formulaire `PatientFormDialog.tsx` pour gérer l'ajout et la suppression dynamique des lignes téléphoniques
- [x] 3.4 Ajouter pour chaque ligne de téléphone la sélection de la relation (dropdown ou saisie libre), le sélecteur de pays avec indicatif et le commutateur WhatsApp

## 4. Frontend - Affichage et Envoi WhatsApp

- [x] 4.1 Mettre à jour la colonne d'identité figée dans `PatientDetail.tsx` pour afficher tous les numéros de téléphone du patient avec leurs badges de relation, badges WhatsApp et le composant `ClickToCopy`
- [x] 4.2 Créer un composant de dialogue Radix/Shadcn pour la sélection du numéro de téléphone destinataire lors de l'envoi WhatsApp
- [x] 4.3 Mettre à jour les boutons d'envoi WhatsApp dans `DocumentsTab.tsx` et `Travaux.tsx` pour ouvrir la boîte de dialogue de sélection si le patient possède plusieurs numéros de téléphone valides avant d'appeler l'API
