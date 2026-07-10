# Fiche Prestataire

## MODIFIED Requirements

### Requirement: Layout en deux colonnes de la fiche prestataire
La fiche d'un prestataire (fournisseur) SHALL adopter une mise en page en deux colonnes :
- Un volet latéral gauche contenant les coordonnées du prestataire (email, téléphone, adresse, notes) et un résumé financier consolidé (`MoneySummary` avec les montants Dû, Réglé, Reste). Les informations de coordonnées (email, téléphone, adresse) SHALL intégrer le mécanisme de copie rapide `ClickToCopy` et SHALL être formatées sans retour à la ligne indésirable.
- Un panneau principal contenant trois onglets (`Tabs`) : "Factures", "Dépenses" et "Règlements".

#### Scenario: Visualisation de la fiche prestataire
- **WHEN** l'utilisateur navigue sur la fiche d'un prestataire existant
- **THEN** l'interface affiche à gauche les informations d'identité et le `MoneySummary`
- **THEN** l'interface affiche à droite les trois onglets "Factures", "Dépenses" et "Règlements"
- **AND** les coordonnées (email, téléphone, adresse) sont affichées avec le composant ClickToCopy pour copie rapide
