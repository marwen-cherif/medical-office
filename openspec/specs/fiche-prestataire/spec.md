# Fiche Prestataire

## Purpose
TBD - Fiche d'un prestataire (fournisseur) contenant son identité, son récap monétaire, ses factures, ses dépenses et ses règlements.

## Requirements

### Requirement: Layout en deux colonnes de la fiche prestataire
La fiche d'un prestataire (fournisseur) SHALL adopter une mise en page en deux colonnes :
- Un volet latéral gauche contenant les coordonnées du prestataire (email, téléphone, adresse, notes) et un résumé financier consolidé (`MoneySummary` avec les montants Dû, Réglé, Reste).
- Un panneau principal contenant trois onglets (`Tabs`) : "Factures", "Dépenses" et "Règlements".

#### Scenario: Visualisation de la fiche prestataire
- **WHEN** l'utilisateur navigue sur la fiche d'un prestataire existant
- **THEN** l'interface affiche à gauche les informations d'identité et le `MoneySummary`
- **THEN** l'interface affiche à droite les trois onglets "Factures", "Dépenses" et "Règlements"

### Requirement: Onglet Règlements de la fiche prestataire
L'onglet "Règlements" SHALL afficher un historique chronologique paginé de tous les règlements (versements) effectués pour le prestataire.
Chaque versement affiché dans la liste SHALL présenter :
- Le montant réglé (formaté en euros avec séparateur de milliers et virgule)
- Le mode de règlement (Virement, Espèces, Chèque, etc.)
- La date du règlement (formatée au format français JJ/MM/AAAA)
- Le libellé de la dépense concernée ou son motif
Si aucun règlement n'a été enregistré pour ce prestataire, un message indiquant "Aucun règlement." SHALL être affiché.

#### Scenario: Affichage de la liste des règlements
- **WHEN** l'utilisateur clique sur l'onglet "Règlements"
- **THEN** l'interface affiche la liste chronologique décroissante des versements du prestataire
- **THEN** chaque ligne de versement présente son montant en vert, son mode de paiement, sa date, et le libellé de la dépense associée

### Requirement: API de liste des règlements d'un prestataire
Le backend SHALL exposer un point d'accès GET sur `/api/prestataires/{prestataire_id}/reglements` acceptant les paramètres de pagination `limit` (optionnel, défaut 20) et `offset` (optionnel, défaut 0).
Ce point d'accès SHALL renvoyer la liste paginée des règlements associés aux dépenses du prestataire, triée par date de règlement décroissante.

#### Scenario: Récupération des règlements via l'API
- **WHEN** le client envoie une requête GET sur `/api/prestataires/1/reglements?limit=10&offset=0`
- **THEN** le serveur répond avec un code de statut 200
- **THEN** la réponse contient la liste d'objets règlements avec les champs `id`, `depense_id`, `depense_libelle`, `montant`, `mode`, `motif`, `date_reglement`, `created_at` et le nombre total de règlements

### Requirement: Dialogue de consultation des règlements d'une dépense
Dans l'onglet "Dépenses", chaque ligne de dépense SHALL proposer un bouton ou une action permettant d'ouvrir un dialogue modal (drawer) listant en détail tous les règlements associés à cette dépense spécifique.
Pour chaque règlement de la dépense, le dialogue SHALL afficher le montant, la date et le mode de règlement.
Si aucun règlement n'a encore été enregistré pour la dépense, le dialogue SHALL afficher un message de liste vide.

#### Scenario: Ouverture du dialogue des règlements d'une dépense
- **WHEN** l'utilisateur clique sur le bouton de consultation des règlements d'une dépense
- **THEN** un dialogue modal s'ouvre et interroge le backend pour obtenir les règlements de cette dépense
- **THEN** le dialogue affiche la liste des règlements individuels effectués (montant, mode, date)

### Requirement: API de récupération des règlements d'une dépense
Le backend SHALL exposer un point d'accès GET sur `/api/depenses/{depense_id}/reglements`.
Ce point d'accès SHALL renvoyer la liste de tous les règlements associés à la dépense spécifiée, triée du plus récent au plus ancien.

#### Scenario: Récupération des règlements d'une dépense via l'API
- **WHEN** le client envoie une requête GET sur `/api/depenses/1/reglements`
- **THEN** le serveur répond avec un code de statut 200 et la liste des règlements de la dépense 1, contenant pour chacun `id`, `depense_id`, `montant`, `mode`, `motif`, `date_reglement`, `created_at`
