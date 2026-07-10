## 1. Backend

- [x] 1.1 Créer les modèles Pydantic `FeaturesSettingsOut` et `FeaturesSettingsIn` dans `apps/api/crm/server.py` avec les champs `whatsapp_api_enabled: bool` et `emailing_enabled: bool`.
- [x] 1.2 Ajouter les routes GET/PUT `/api/settings/features` dans `apps/api/crm/server.py` pour lire et écrire les feature flags dans la table `meta` (`emailing_enabled` par défaut à `True`, `whatsapp_api_enabled` par défaut à `False`).
- [x] 1.3 Modifier les modèles `WhatsAppSettingsOut`/`WhatsAppSettingsIn` et les endpoints GET/PUT `/api/settings/whatsapp` dans `apps/api/crm/server.py` pour en retirer le champ `whatsapp_api_enabled`.
- [x] 1.4 Modifier la fonction d'envoi d'email `send` dans `apps/api/crm/routers/documents.py` pour vérifier `emailing_enabled` dans la table `meta` et lever une `ApiError` si le flag est à faux.
- [x] 1.5 Modifier l'envoi de WhatsApp `send_whatsapp` dans `apps/api/crm/routers/documents.py` pour lire l'état de `whatsapp_api_enabled` directement de la table `meta` et lever une erreur si désactivé.

## 2. Frontend

- [x] 2.1 Mettre à jour les types TS de l'API dans `apps/web/src/api/schema.d.ts` suite à la modification des modèles Pydantic backend.
- [x] 2.2 Ajouter les hooks React Query `useFeatureSettings()` et `useSetFeatureSettings()` dans `apps/web/src/hooks/queries.ts`.
- [x] 2.3 Mettre à jour le composant `FonctionnalitesTab.tsx` pour utiliser les nouveaux hooks de fonctionnalités, avec des cases à cocher pour activer/désactiver Meta WhatsApp Cloud d'une part, et l'Emailing d'autre part.
- [x] 2.4 Mettre à jour `Parametrage.tsx` pour récupérer les statuts des fonctionnalités via `useFeatureSettings()` et masquer l'onglet « Modèles d'email » si `emailing_enabled` est désactivé, et l'onglet « WhatsApp » si `whatsapp_api_enabled` est désactivé.
- [x] 2.5 Modifier `DocumentsTab.tsx` (dans `apps/web/src/screens/patient-detail/`) pour conditionner la visibilité de l'action « Envoyer par email » à la valeur de `emailing_enabled`, en plus de conditionner WhatsApp à `whatsapp_api_enabled`.
- [x] 2.6 Modifier `Travaux.tsx` (dans `apps/web/src/screens/`) pour conditionner le bouton d'envoi par email à `emailing_enabled`, en plus de conditionner WhatsApp à `whatsapp_api_enabled`.

## 3. Vérification et validation

- [x] 3.1 Régénérer le schéma OpenAPI (`apps/web/openapi.json`) et le client TypeScript (`schema.d.ts`).
- [x] 3.2 Vérifier le bon fonctionnement global de l'activation/désactivation des flags et l'impact direct sur l'interface graphique.
