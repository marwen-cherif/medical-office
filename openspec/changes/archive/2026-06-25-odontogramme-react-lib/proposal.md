## Why

L'odontogramme de saisie de l'UI React (`ui/src/components/common/Odontogramme.tsx`) est une
grille de boutons numérotés (notation FDI) : efficace pour **saisir** les dents d'un acte
(numéros FDI permanents, indispensables à la frappe rapide), mais la fiche patient n'offre
**aucune représentation anatomique** permettant de **visualiser d'un coup d'œil l'état dentaire**
(dents déjà traitées, dents planifiées). On veut ajouter cette lecture clinique synthétique en
s'appuyant sur un composant React dédié, **`react-odontogram`** (schéma dentaire SVG réaliste,
notation FDI, colorisation par condition), **sans dégrader** l'ergonomie de saisie existante.

## What Changes

- **Conserver inchangée** la grille numérotée actuelle (`Odontogramme.tsx`) pour la **saisie**
  d'un acte : numéros FDI affichés **en permanence**, bascule Adulte/Enfant, API contrôlée
  `value`/`onChange`. Les quatre points d'appel (`ActeCard` → `PrestationDialog`, `PlanDialog`,
  `GenerateDialog`) restent **strictement identiques**.
- **Ajouter un nouveau composant de visualisation en lecture seule** s'appuyant sur
  `react-odontogram` (`readOnly`, `teethConditions`) : un **schéma anatomique colorisé** affiché
  en **section dédiée sur la fiche patient** (onglet Plans & actes). Les dents portées par des
  **actes réalisés** et par des **actes planifiés** sont distinguées par des couleurs/légendes
  distinctes, dérivées des données cliniques existantes (`clinical`). Le numéro FDI d'une dent
  s'affiche **au survol** (infobulle), comportement natif de la librairie pour cette vue.
- **Survol d'un acte → mise en évidence** : survoler la ligne d'un acte dans la liste (actes
  isolés / plans) **met en évidence** les dents concernées sur le schéma (couleur prioritaire,
  transitoire).
- **Préserver le modèle de données** : les dents proviennent du champ `prestations.dents` déjà
  persisté — **aucune** migration de schéma, **aucun** changement d'API backend, **aucune**
  nouvelle requête.
- **Ajouter la dépendance** `react-odontogram` à `ui/package.json` (+ import de sa feuille de
  style).

## Capabilities

### New Capabilities

_(aucune nouvelle capability : la visualisation enrichie étend la capability existante
`selection-dents`, qui couvre déjà le composant odontogramme.)_

### Modified Capabilities

- `selection-dents` : **ajout** d'une exigence couvrant un **mode visualisation en lecture
  seule** de l'odontogramme — schéma anatomique (via `react-odontogram`) colorisant les dents
  selon leur état clinique (réalisé / planifié), affiché sur la fiche patient. L'odontogramme de
  **saisie** (grille numérotée native, numéros permanents, bascule Adulte/Enfant, persistance
  FDI, tolérance des jetons non-FDI) reste **inchangé** : aucune exigence existante n'est
  modifiée ni supprimée.

## Impact

- **Front-end (React/`ui/`)** :
  - **Nouveau** composant de visualisation lecture seule (ex.
    `ui/src/components/common/OdontogrammeClinique.tsx`) encapsulant `react-odontogram`.
  - `ui/src/screens/patient-detail/PlansActesTab.tsx` — insertion de la section visualisation
    (alimentée par les données `clinical` déjà chargées).
  - `ui/package.json` / `package-lock.json` — ajout de `react-odontogram` + import CSS.
  - **Aucun** changement à `Odontogramme.tsx`, `ActeCard.tsx`, `PrestationDialog.tsx`,
    `PlanDialog.tsx`, `GenerateDialog.tsx`.
- **Back-end / données** : **aucun** changement (modèle `prestations.dents`, API `clinical`,
  schéma SQLite inchangés). Pas de migration.
- **Dépendances** : ajout de `react-odontogram` (peer deps React/React-DOM déjà présentes en
  v19). Risques à lever à l'implémentation : compatibilité React 19 et correspondance exacte des
  numéros FDI temporaires (51–85) renvoyés par la librairie.
- **Plateformes** : rendu identique attendu en desktop (Tauri/WebView) et web (navigateur),
  composant purement React/SVG.
