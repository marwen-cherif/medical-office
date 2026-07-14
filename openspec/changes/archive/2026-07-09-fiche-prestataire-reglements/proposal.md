## Why

Actuellement, l'interface de la fiche prestataire présente les informations de façon linéaire et n'affiche nulle part l'historique et le détail des règlements effectués (par virement, espèces, chèque, etc.) pour ses différentes dépenses, notamment en cas de règlement partiel. Pour améliorer le suivi de la trésorerie et s'aligner sur l'ergonomie générale de l'application, il est nécessaire de restructurer cette vue en s'inspirant du layout à onglets de la fiche patient, et d'y ajouter un onglet dédié à l'historique des règlements.

## What Changes

- **Layout à deux colonnes (inspiration fiche patient)** :
  - Un volet latéral gauche (ou droit) pour la carte d'identité (Email, Téléphone, Adresse, Notes) et le résumé de trésorerie (`MoneySummary` : Dû, Réglé, Reste).
  - Une zone principale avec des onglets (`Tabs`) : "Factures", "Dépenses" et "Règlements".
- **Nouvel onglet "Règlements"** :
  - Affiche la liste chronologique des règlements effectués pour ce prestataire.
  - Détaille pour chaque règlement : le montant versé, le mode de paiement (espèces, virement, etc.), la date du règlement, et le libellé de la dépense concernée.
  - Supporte la pagination.
- **Consultation des règlements par dépense** :
  - Dans l'onglet "Dépenses", ajout d'une action pour ouvrir un dialogue (drawer) affichant l'historique détaillé des règlements associés à une dépense spécifique.
- **API et Données** :
  - Exposition d'une route FastAPI `/api/prestataires/{prestataire_id}/reglements` pour lister et paginer les règlements globaux du prestataire.
  - Exposition d'une route FastAPI `/api/depenses/{depense_id}/reglements` pour obtenir la liste des règlements spécifiques d'une dépense.
  - Implémentation des requêtes correspondantes dans `crm/repo.py`.

## Capabilities

### New Capabilities
- `fiche-prestataire`: Gestion de la mise en page de la fiche prestataire en colonnes et onglets, intégrant le suivi consolidé, l'historique détaillé des règlements de dépenses, ainsi que le détail par dépense dans un dialogue.

### Modified Capabilities
*Aucune capacité existante n'est modifiée car les dépenses et prestataires ne font pas l'objet de spécifications existantes dans `openspec/specs/`.*

## Impact

- **Backend FastAPI** :
  - `crm/repo.py` : Fonctions pour lister et compter les règlements d'un prestataire, ainsi que pour récupérer les règlements d'une dépense (déjà existante en Python sous `repo.list_reglements(conn, depense_id)` mais non exposée).
  - `crm/routers/prestataires.py` : Routes GET `/api/prestataires/{prestataire_id}/reglements` et GET `/api/depenses/{depense_id}/reglements` avec modèles Pydantic associés.
- **Frontend React** :
  - `ui/src/hooks/prestataires.ts` : Nouveaux hooks TanStack Query `useProviderReglements` et `useDepenseReglements`.
  - `ui/src/screens/PrestataireDetail.tsx` : Refonte du layout (aside + tabs) et ajout de l'action de consultation sur la liste des dépenses.
  - `ui/src/components/dialogs/DepenseReglementsDialog.tsx` : Nouveau composant pour afficher l'historique des règlements d'une dépense en format dialogue (drawer).
  - `ui/src/screens/prestataire-detail/ReglementsTab.tsx` : Nouveau composant d'onglet pour lister les règlements d'un prestataire.
