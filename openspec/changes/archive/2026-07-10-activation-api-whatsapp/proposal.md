## Why

Actuellement, tous les onglets de paramétrage sont toujours visibles, même si le cabinet n'utilise pas certaines fonctionnalités complexes comme l'API WhatsApp Meta Cloud. Pour épurer l'interface, il est préférable de regrouper les activations de fonctionnalités optionnelles sous un onglet unique « Fonctionnalités » (Feature Flags). L'onglet de paramétrage de l'API WhatsApp Meta Cloud ne doit apparaître dans la barre latérale des réglages que si la fonctionnalité a été activée au préalable dans cet onglet.

## What Changes

- **Paramétrage › Fonctionnalités (Nouvel Onglet)** : Ajout d'un nouvel onglet regroupant l'activation des fonctionnalités optionnelles, avec pour le moment la fonctionnalité « API WhatsApp Meta Cloud ».
- **Paramétrage › Navigation** : L'onglet « WhatsApp » de configuration technique de l'API Meta n'est affiché dans le sous-menu de paramétrage que si « API WhatsApp Meta Cloud » est cochée dans l'onglet « Fonctionnalités ».
- **Fiche Patient & Liste Documents** : Le bouton « Envoyer par WhatsApp (Meta) » est visible uniquement si l'option est activée.

## Capabilities

### New Capabilities
- `activation-fonctionnalites` : Gestion de l'activation/désactivation des fonctionnalités optionnelles du cabinet (feature flags) et conditionnement dynamique de la barre latérale de paramétrage et de l'UI d'envoi.

## Impact

- **API Backend** :
  - L'activation est persistée via `whatsapp_api_enabled` en base de données.
- **Frontend React** :
  - Création du composant `FonctionnalitesTab.tsx` pour gérer le nouvel onglet.
  - Ajout de l'onglet « Fonctionnalités » dans le sous-menu de Paramétrage.
  - Conditionnement de l'onglet « WhatsApp » dans la liste des onglets de Paramétrage.
  - Conditionnement du bouton d'envoi Meta Cloud sur les documents.
