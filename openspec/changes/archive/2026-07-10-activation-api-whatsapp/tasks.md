## 1. Backend (Python/FastAPI)

- [x] 1.1 Étendre les modèles Pydantic `WhatsAppSettingsOut` et `WhatsAppSettingsIn` dans `server.py` pour ajouter le champ `whatsapp_api_enabled: bool`
- [x] 1.2 Mettre à jour l'endpoint GET `/api/settings/whatsapp` pour retourner `whatsapp_api_enabled` (valeur par défaut : `False` si non configurée)
- [x] 1.3 Mettre à jour l'endpoint PUT `/api/settings/whatsapp` pour persister `whatsapp_api_enabled` sous forme de `"true"` ou `"false"` dans la table `meta`
- [x] 1.4 Modifier l'action d'envoi dans `documents.py` (`send_whatsapp`) pour bloquer l'appel si `whatsapp_api_enabled` est à faux

## 2. Frontend (React/TypeScript)

- [x] 2.1 Modifier `schema.d.ts` dans `apps/web/src/api/schema.d.ts` pour déclarer `whatsapp_api_enabled: boolean` dans les types `WhatsAppSettingsIn` et `WhatsAppSettingsOut`
- [x] 2.2 Créer le composant `FonctionnalitesTab.tsx` dans `apps/web/src/screens/parametrage/FonctionnalitesTab.tsx` pour gérer l'activation du drapeau `whatsapp_api_enabled`
- [x] 2.3 Intégrer l'onglet « Fonctionnalités » dans `Parametrage.tsx` (dans les onglets et la navigation)
- [x] 2.4 Conditionner l'affichage de l'onglet « WhatsApp » dans la liste des onglets de `Parametrage.tsx` d'après le paramètre `whatsapp_api_enabled`
- [x] 2.5 Nettoyer `WhatsAppTab.tsx` pour retirer la checkbox redondante
- [x] 2.6 Modifier `DocumentsTab.tsx` pour conditionner la visibilité du bouton « Envoyer par WhatsApp (Meta) » à `waSettings.data?.whatsapp_api_enabled`
- [x] 2.7 Modifier `Travaux.tsx` de la même manière pour masquer le bouton d'envoi Meta Cloud si la fonctionnalité est inactive
