## Context

L'application Cabinet-CRM permet actuellement d'envoyer des documents par email via Mailjet et par WhatsApp via l'API officielle Meta Cloud. Un feature flag existant (`whatsapp_api_enabled`) permet d'activer ou désactiver WhatsApp. L'utilisateur souhaite ajouter un feature flag similaire pour l'emailing (`emailing_enabled`) afin de pouvoir le désactiver complètement dans l'onglet « Fonctionnalités » (Feature Flags) et masquer toutes les interfaces d'emailing du CRM. De plus, il a été décidé d'isoler la gestion globale des fonctionnalités (Feature Flagging) sous un endpoint générique plutôt que de surcharger les endpoints WhatsApp.

## Goals / Non-Goals

**Goals:**
- Ajouter une option d'activation/désactivation de la fonctionnalité d'emailing (`emailing_enabled`).
- Créer un endpoint dédié `/api/settings/features` pour lire et modifier l'état des modules optionnels.
- Migrer le flag existant `whatsapp_api_enabled` vers cet endpoint.
- Persister l'état de `emailing_enabled` dans la table `meta` avec une valeur par défaut à `true`.
- Conditionner l'interface utilisateur frontend (masquer l'onglet « Modèles d'email » dans le paramétrage, masquer le bouton « Envoyer par email » sur les documents et les travaux) lorsque le flag est désactivé.
- Bloquer toute tentative d'envoi d'email au niveau du backend (endpoint `/documents/{document_id}/send`) si le flag est à faux.

**Non-Goals:**
- Supprimer les données de modèles d'email de la base de données ou du disque lors de la désactivation.
- Modifier d'autres protocoles de messagerie.

## Decisions

1. **Création d'un nouvel endpoint de paramétrage `/api/settings/features` :**
   - Rationale : Permet une gestion centralisée et propre des feature flags, indépendante des configurations techniques spécifiques (ex. tokens, template IDs).
   - GET `/api/settings/features` retourne :
     - `whatsapp_api_enabled: bool` (depuis `meta`, défaut `false`)
     - `emailing_enabled: bool` (depuis `meta`, défaut `true` si non défini pour assurer la compatibilité ascendante).
   - PUT `/api/settings/features` accepte ces deux drapeaux et les écrit en base de données dans la table `meta`.

2. **Nettoyage de l'endpoint WhatsApp :**
   - Retirer le champ `whatsapp_api_enabled` des modèles `WhatsAppSettingsOut` et `WhatsAppSettingsIn` et des endpoints GET/PUT `/api/settings/whatsapp`.

3. **Création des hooks frontend dédiés :**
   - Ajouter `useFeatureSettings()` et `useSetFeatureSettings()` dans `apps/web/src/hooks/queries.ts` pour appeler ce nouvel endpoint.

4. **Conditionnement UI au niveau du Frontend :**
   - Dans `Parametrage.tsx`, utiliser la valeur de `emailing_enabled` récupérée du hook `useFeatureSettings()` pour afficher/masquer l'onglet `emails` (« Modèles d'email ») et `whatsapp_api_enabled` pour l'onglet WhatsApp.
   - Dans `DocumentsTab.tsx` (fiche patient) et `Travaux.tsx` (travaux en cours), conditionner le rendu du bouton d'envoi par email en vérifiant si `emailing_enabled` est vrai.
   - Dans `FonctionnalitesTab.tsx`, utiliser les nouveaux hooks pour afficher et modifier l'activation de Meta WhatsApp Cloud et de l'emailing.

5. **Validation Backend dans le routeur documents :**
   - Dans `apps/api/crm/routers/documents.py`, lever une erreur HTTP 400 dans l'endpoint POST `/documents/{document_id}/send` si `emailing_enabled` est désactivé.
   - Dans l'envoi de WhatsApp, interroger la table `meta` pour vérifier `whatsapp_api_enabled`.

## Risks / Trade-offs

- **Compatibilité de l'API :** Retirer un champ d'un endpoint existant (`/api/settings/whatsapp`) est techniquement un changement de structure d'API, mais comme nous mettons à jour simultanément le backend et le frontend dans ce monorepo et que l'API est consommée uniquement en local par l'application, le risque est nul et cela permet de garder un code propre et maintenable à long terme.
