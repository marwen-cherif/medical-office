## 1. Backend (FastAPI & repo)

- [x] 1.1 Ajouter la fonction `list_prestataire_reglements(conn, prestataire_id, limit, offset)` dans [repo.py](file:///c:/Users/dorki/WebstormProjects/medical-office/crm/repo.py) pour interroger les lignes de règlement du prestataire.
- [x] 1.2 Ajouter la fonction `count_prestataire_reglements(conn, prestataire_id)` dans [repo.py](file:///c:/Users/dorki/WebstormProjects/medical-office/crm/repo.py) pour compter les lignes de règlement du prestataire.
- [x] 1.3 Définir les modèles Pydantic `PrestataireReglementOut`, `PrestataireReglementListOut` et `DepenseReglementOut` dans [prestataires.py](file:///c:/Users/dorki/WebstormProjects/medical-office/crm/routers/prestataires.py).
- [x] 1.4 Implémenter le point d'accès GET `/api/prestataires/{prestataire_id}/reglements` dans [prestataires.py](file:///c:/Users/dorki/WebstormProjects/medical-office/crm/routers/prestataires.py).
- [x] 1.5 Implémenter le point d'accès GET `/api/depenses/{depense_id}/reglements` dans [prestataires.py](file:///c:/Users/dorki/WebstormProjects/medical-office/crm/routers/prestataires.py) (pour la liste des versements d'une seule dépense).

## 2. Frontend Hooks & Types

- [x] 2.1 Mettre à jour `ui/src/api/types.ts` (ou équivalent) pour ajouter les types `PrestataireReglement` et `DepenseReglement`.
- [x] 2.2 Créer les hooks TanStack Query `useProviderReglements` et `useDepenseReglements` dans [prestataires.ts](file:///c:/Users/dorki/WebstormProjects/medical-office/ui/src/hooks/prestataires.ts).

## 3. Interface de la Fiche Prestataire (Layout & Onglet Règlements)

- [x] 3.1 Refondre [PrestataireDetail.tsx](file:///c:/Users/dorki/WebstormProjects/medical-office/ui/src/screens/PrestataireDetail.tsx) pour basculer sur un layout à deux colonnes (aside pour les coordonnées et la synthèse financière, zone principale pour les onglets).
- [x] 3.2 Intégrer les sections de factures et dépenses existantes dans des onglets distincts ("Factures" et "Dépenses") au sein de la zone principale.
- [x] 3.3 Créer le composant d'onglet `ReglementsTab` (dans un nouveau fichier [ReglementsTab.tsx](file:///c:/Users/dorki/WebstormProjects/medical-office/ui/src/screens/prestataire-detail/ReglementsTab.tsx) ou directement dans `PrestataireDetail.tsx`) affichant la liste paginée des règlements avec montant, mode, date et libellé de dépense.
- [x] 3.4 Créer le composant de dialogue [DepenseReglementsDialog.tsx](file:///c:/Users/dorki/WebstormProjects/medical-office/ui/src/components/dialogs/DepenseReglementsDialog.tsx) pour lister l'historique des règlements d'une dépense sélectionnée.
- [x] 3.5 Ajouter un bouton ou une action (icône d'historique) sur chaque ligne de dépense dans l'onglet Dépenses pour ouvrir le dialogue `DepenseReglementsDialog`.
- [x] 3.6 Ajouter le nouvel onglet "Règlements" à la liste des onglets de la fiche prestataire.
