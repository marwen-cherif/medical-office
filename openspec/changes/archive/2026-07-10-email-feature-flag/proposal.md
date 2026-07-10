## Why

Permettre aux utilisateurs de désactiver complètement la fonctionnalité d'envoi d'emails et la gestion des modèles d'email depuis l'onglet « Fonctionnalités », afin d'épurer l'interface du CRM pour les cabinets n'utilisant pas les emails. De plus, cela introduit une gestion propre et extensible des drapeaux de fonctionnalités (Feature Flags) via un endpoint dédié, évitant de surcharger les réglages spécifiques (comme WhatsApp).

## What Changes

- Introduction d'un nouvel endpoint de paramétrage dédié aux fonctionnalités : GET/PUT `/api/settings/features`.
- Migration du drapeau `whatsapp_api_enabled` vers cet endpoint global de fonctionnalités.
- Ajout du feature flag `emailing_enabled` (activé par défaut) stocké en base de données dans la table `meta` et exposé par ce nouvel endpoint.
- Ajout d'une case à cocher dans l'onglet « Fonctionnalités » du paramétrage pour activer ou désactiver l'emailing (qui s'ajoute à celle de WhatsApp API).
- Masquage de l'onglet « Modèles d'email » dans le paramétrage si la fonctionnalité est désactivée.
- Masquage de l'action « Envoyer par email » sur les documents (fiches patients et liste des travaux) si la fonctionnalité est désactivée.
- Blocage au niveau du backend de l'envoi d'emails si `emailing_enabled` est désactivé.

## Capabilities

### New Capabilities

### Modified Capabilities

- `activation-fonctionnalites`: Extension pour centraliser la gestion des fonctionnalités optionnelles sous un nouvel endpoint et conditionner l'affichage et l'accès à la fonctionnalité d'emailing et de modèles d'email d'après le drapeau `emailing_enabled`.

## Impact

- `apps/api/crm/server.py`: Création de nouveaux schémas Pydantic `FeaturesSettingsOut` et `FeaturesSettingsIn` et des endpoints GET/PUT `/api/settings/features`. Suppression de `whatsapp_api_enabled` de `WhatsAppSettingsOut` et `WhatsAppSettingsIn`.
- `apps/api/crm/routers/documents.py`: Validation de l'état du flag avant d'autoriser l'envoi d'un email, et mise à jour de la vérification de l'activation WhatsApp via le nouvel état global des fonctionnalités.
- `apps/web/src/screens/Parametrage.tsx`: Masquage dynamique de l'onglet « Modèles d'email » d'après le flag `emailing_enabled`.
- `apps/web/src/screens/parametrage/FonctionnalitesTab.tsx`: Migration vers le nouvel endpoint des fonctionnalités et ajout d'un contrôle pour le flag `emailing_enabled`.
- `apps/web/src/screens/patient-detail/DocumentsTab.tsx`: Masquage dynamique de l'action d'envoi par email d'après le flag.
- `apps/web/src/screens/Travaux.tsx`: Masquage dynamique du bouton d'envoi par email d'après le flag.
