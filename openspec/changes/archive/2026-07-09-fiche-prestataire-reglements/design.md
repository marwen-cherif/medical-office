## Context

L'application Cabinet CRM permet de suivre les dépenses des prestataires. Ces dépenses peuvent faire l'objet de règlements partiels. Bien que les règlements soient stockés de façon atomique dans la table `depense_reglements`, l'interface utilisateur de la fiche prestataire affiche uniquement les dépenses consolidées et le montant total réglé. Il n'existe pas d'interface pour lister tous les règlements individuels effectués pour un prestataire. De plus, la fiche prestataire actuelle a un layout linéaire vertical simple (une seule colonne) qui diffère de la fiche patient à deux colonnes (informations d'identité et soldes dans une barre latérale, activités dans des onglets).

## Goals / Non-Goals

**Goals:**
- Proposer une refonte visuelle de la fiche prestataire en adoptant un layout à deux colonnes similaire à la fiche patient.
- Ajouter un nouvel onglet "Règlements" sur la fiche prestataire affichant l'historique détaillé et paginé des versements.
- Fournir une API propre pour récupérer cet historique depuis le backend FastAPI.

**Non-Goals:**
- Modifier le processus de création de dépenses ou de saisie de règlement (l'action "Régler" sur une dépense reste inchangée).
- Permettre la suppression ou la modification d'un règlement individuel depuis le nouvel onglet (les règlements sont liés aux dépenses de manière read-only pour cet onglet).

## Decisions

### 1. Structure de données et requête SQL de listing des règlements
Nous introduisons de nouvelles requêtes au niveau de `crm/repo.py` pour récupérer et compter les règlements d'un prestataire.
- **Requête SQL** :
  ```sql
  SELECT r.id, r.depense_id, r.montant, r.mode, r.motif, r.date_reglement, r.created_at, d.libelle as depense_libelle
  FROM depense_reglements r
  JOIN depenses d ON r.depense_id = d.id
  WHERE d.prestataire_id = ?
  ORDER BY date(r.date_reglement) DESC, r.id DESC
  ```
- **Raison** : Permet d'obtenir directement les règlements triés de manière chronologique avec le libellé de la dépense d'origine. L'alternative de filtrer côté client après avoir chargé toutes les dépenses est rejetée car elle ne permettrait pas une pagination efficace en base de données.

### 2. Point d'accès API GET `/api/prestataires/{prestataire_id}/reglements` et GET `/api/depenses/{depense_id}/reglements`
Exposition de deux endpoints de règlements dans `crm/routers/prestataires.py`.
- **Modèle Pydantic de retour global (`PrestataireReglementOut`)** :
  ```python
  class PrestataireReglementOut(BaseModel):
      id: int
      depense_id: int
      depense_libelle: Optional[str] = None
      montant: float
      mode: Optional[str] = None
      motif: Optional[str] = None
      date_reglement: Optional[str] = None
      created_at: Optional[str] = None
  ```
- **Modèle Pydantic de retour spécifique à une dépense (`DepenseReglementOut`)** :
  ```python
  class DepenseReglementOut(BaseModel):
      id: int
      depense_id: int
      montant: float
      mode: Optional[str] = None
      motif: Optional[str] = None
      date_reglement: Optional[str] = None
      created_at: Optional[str] = None
  ```
- **Raison** : Cohérence avec l'API existante et typage fort pour le client TypeScript. Le endpoint par dépense réutilise la fonction `repo.list_reglements` déjà existante et testée.

### 3. Layout à deux colonnes de `PrestataireDetail.tsx` et dialogue spécifique
- La fiche prestataire est restructurée avec la même grille Tailwind que la fiche patient :
  - `<aside className="space-y-4 lg:w-72 lg:shrink-0">` à gauche pour l'identité (`IdentityCard`) et la synthèse financière (`MoneySummary` en disposition `column`).
  - `<div className="min-w-0 flex-1">` à droite contenant un composant `Tabs` de Radix UI (déjà importé/disponible).
- Les onglets affichés sont :
  - **Factures** : Affiche le composant existant `FacturesSection`.
  - **Dépenses** : Affiche le composant existant `DepensesSection`, sur lequel nous ajoutons un bouton ou une action (icône d'historique/détail) sur chaque ligne de dépense non réglée ou partiellement réglée. Cette action ouvre `DepenseReglementsDialog`.
  - **Règlements** : Affiche le nouveau composant `ReglementsTab` propre au prestataire.
- **Dialogue de détail (`DepenseReglementsDialog.tsx`)** :
  - Un nouveau composant dans `ui/src/components/dialogs/` utilisant la structure standard `<Dialog>` de l'application. Il affiche la liste des règlements individuels pour la dépense sélectionnée (montant, date, mode) dans un format propre et structuré.

## Risks / Trade-offs

- **[Risk] Cohérence de l'affichage en cas de dépenses sans libellé** : Si une dépense n'a pas de libellé ou de motif, le règlement associé pourrait afficher une ligne vide dans le listing global.
  - *Mitigation* : Utiliser le motif (`motif`) ou une valeur par défaut comme "Dépense sans libellé" ou le libellé générique de la dépense.
- **[Risk] Désalignement avec le mode Flet historique** : L'interface Flet historique n'est plus maintenue activement (comme indiqué dans CLAUDE.md, seul le CRM React/Tauri est ciblé).
  - *Mitigation* : Les modifications se concentrent uniquement sur le code du serveur FastAPI et l'application React dans `ui/`.
