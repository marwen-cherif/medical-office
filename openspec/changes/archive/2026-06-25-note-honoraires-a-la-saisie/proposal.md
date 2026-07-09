## Why

Aujourd'hui, saisir un acte (ou un plan + ses actes) et **générer la note d'honoraires**
correspondante sont deux gestes séparés : on enregistre l'acte, la fenêtre se ferme, puis il
faut rouvrir « Note d'honoraires », repasser en mode sélection et re-cocher les actes qu'on
vient justement de créer. Pour le cas courant « je saisis l'acte du jour et je remets sa note
au patient (à l'écran ou imprimée) », c'est trois étapes de trop. On veut **enchaîner** la
génération (et l'impression) directement depuis la fenêtre de saisie, **sans retirer** la
possibilité de simplement enregistrer l'acte.

## What Changes

- Les fenêtres de **création** « Nouvel acte » (`PrestationDialog`) et « Nouveau plan + ses
  actes » (`PlanDialog`) proposent désormais **deux issues** au lieu d'un seul bouton
  « Enregistrer » :
  1. **Enregistrer seulement** (comportement actuel, inchangé et par défaut) ;
  2. **Enregistrer + générer la note d'honoraires**.
- Pour l'issue 2, après création des actes, la **fenêtre de génération de note** s'ouvre
  **pré-remplie** avec **exactement les actes qui viennent d'être créés** (pré-cochés).
  L'utilisateur confirme/choisit le modèle puis valide. Le choix « générer » ou « générer et
  imprimer » se fait **dans cette fenêtre** (elle expose déjà les deux boutons) : inutile de le
  dupliquer à l'enregistrement, ce qui n'apporterait rien.
- Aucune création de note « silencieuse » : la note passe toujours par la fenêtre de
  génération existante (choix du modèle, montants de note éditables, totaux), donc rien n'est
  généré ni imprimé sans confirmation explicite.
- **Aucun nouveau réglage**, **aucune route backend**, **aucune migration** : la fonctionnalité
  réutilise telles quelles la génération de note adossée aux actes, l'impression et la règle
  « pas de paiement créé pour une note adossée à des actes ».

## Capabilities

### New Capabilities

- `note-honoraires-a-la-saisie`: depuis les fenêtres de création d'acte / de plan, offrir le
  choix « enregistrer seul » / « enregistrer + générer la note », et, pour le second, ouvrir la
  note d'honoraires **pré-remplie sur les actes nouvellement créés** (le choix imprimer / ne pas
  imprimer se fait dans la fenêtre de note).

### Modified Capabilities

<!-- Aucune. La capability `facturation-multi-lignes` reste inchangée : la note d'honoraires
     présente déjà les actes pré-cochés et n'a pas besoin d'évoluer. Ce changement n'ajoute
     qu'un point d'entrée et un enchaînement réutilisant son comportement existant. -->

## Impact

- **UI React uniquement** :
  - `ui/src/screens/patient-detail/PrestationDialog.tsx` et `PlanDialog.tsx` : le bouton
    d'enregistrement devient une action à trois choix (split-button / menu) ; après succès,
    remonter au parent les `prestation_id` créés et l'intention.
  - `ui/src/screens/patient-detail/PlansActesTab.tsx` : orchestration — à réception des actes
    créés, ouvrir `GenerateDialog` en mode `note` avec `initialSelection` = ces actes et
    l'intention.
  - `ui/src/screens/patient-detail/GenerateDialog.tsx` : aucune prop d'intention ; la fenêtre
    expose comme avant « Générer » et « Générer et imprimer » et l'utilisateur choisit. La
    pré-sélection du modèle de note quand il est unique est déjà gérée via `initialSelection`.
- **Backend Python** : inchangé. La route `POST …/documents/generate` accepte déjà
  `selected_prestation_ids` + `do_print` ; la règle « note adossée à des actes ⇒ aucune
  créance » (`generator.create_note_creance`) s'applique automatiquement, sans double-comptage
  de la dette.
- **Données / schéma** : aucun changement (pas de colonne, pas de migration, pas de
  `SCHEMA_VERSION`).
