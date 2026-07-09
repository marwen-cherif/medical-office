## 1. Dépendance et spike de vérification

- [x] 1.1 Ajouter `react-odontogram` (version épinglée `0.5.6`, `--save-exact`) à `ui/package.json` et installer. Peer `react >=17` ⇒ React 19 compatible, pas d'`overrides`.
- [x] 1.2 Importer la feuille de style `react-odontogram/style.css` (en tête de `OdontogrammeClinique.tsx`).
- [x] 1.3 Spike (types `dist/index.d.ts` + bundle + story `zBaby.stories.tsx`) : ids `"teeth-<…>"` ; dents de lait via `maxTeeth=5` mais numérotées en quadrants 1-4 ⇒ mapping FDI 51-85 requis ; React 19 OK.

## 2. Helpers de mapping FDI ↔ librairie

- [x] 2.1 Créer les helpers déterministes : `fdiToToothId(fdi, denture)` (adulte `^[1-4][1-8]$` → `"teeth-<fdi>"` ; enfant `^[5-8][1-5]$` → `"teeth-<quadrant-4><position>"` ; sinon `null` = hors-schéma) et `toothIdToFdi(id, denture)` pour l'infobulle (enfant : `quadrant+4`).
- [x] 2.2 Couleurs de la palette de l'app (cf. `index.css`) passées en `fillColor`/`outlineColor` : réalisé `#10357f` (navy), planifié `#62ebe2`/`#0c8b82` (teal / teal-dark).

## 3. Composant de visualisation clinique (lecture seule)

- [x] 3.1 Créer `ui/src/components/common/OdontogrammeClinique.tsx` : `Odontogram` en `readOnly`, `showLabels`, `notation="FDI"`, `layout="square"`, `maxTeeth` selon la denture ; `tooltip.content` personnalisé affichant la vraie FDI + l'état.
- [x] 3.2 Fonction `deriveOdontogramme(clinical, denture)` : `isoles` + `plans[].prestations`, `parseDents`, classement **réalisé** (acte daté) / **planifié** (réalisé prioritaire), mapping via `fdiToToothId`, deux `teethConditions` + liste hors-schéma. Déduplication.
- [x] 3.3 Rendu de la **liste texte hors-schéma** sous le schéma (dents de lait chez l'adulte, dents permanentes chez l'enfant, jetons non-FDI), groupée réalisé/planifié ; cas « aucune dent » = schéma neutre sans liste.

## 4. Intégration dans la fiche patient

- [x] 4.1 Section visualisation insérée en tête de l'onglet **Plans & actes** (`PlansActesTab.tsx`), au-dessus des notes/actes, alimentée par `clinical.data` + `denture` déjà disponibles.
- [x] 4.2 Rafraîchissement automatique : `useMemo([clinical, denture])` + invalidation TanStack Query (`invalidatePatient`) déjà en place après chaque mutation d'acte.
- [x] 4.3 En-tête épinglé : barre d'actions + odontogramme dans un conteneur `sticky top-0 z-20` (fond `bg-bg`), accroché au `<main overflow-auto>` du `Shell` ; largeur du schéma bornée (`max-w-sm`) pour rester compact et ne pas masquer la liste.

## 5. Survol d'un acte → mise en évidence

- [x] 5.1 Remonter l'état de survol dans `PlansActesTab` (`hoverFdis`) ; `PrestationRow` émet `onHover(parseDents(pres.dents))` au survol et `onHover(null)` à la sortie (actes isolés + plans).
- [x] 5.2 `OdontogrammeClinique` accepte `highlightFdis` et ajoute un groupe `teethConditions` ambre en dernier (prioritaire, transitoire) ; surlignage des entrées hors-schéma ; légende native désactivée au profit d'une légende maison.

## 6. Recette et finalisation

- [x] 6.1 Saisie **inchangée** : `Odontogramme.tsx`, `ActeCard.tsx`, `PrestationDialog.tsx`, `PlanDialog.tsx`, `GenerateDialog.tsx` non modifiés (numéros FDI permanents préservés).
- [x] 6.2 `npm run typecheck` et `npm run build` **OK** (CSS de la lib bundlé, aucune erreur de types).
- [x] 6.3 Recette manuelle **desktop (Tauri)** et **web** (gate visuel manuel) : patient adulte (11-48 colorées), patient enfant (dents de lait 51-85 colorées + survol affichant la vraie FDI), denture mixte (liste hors-schéma), **survol d'un acte ⇒ dents en ambre**, **en-tête épinglé au défilement d'une longue liste**, légende, cas « aucune dent », mise à jour après mutation.
- [x] 6.4 Aucun changement backend / migration (seuls `ui/` + `package.json`/lock modifiés) ; `ui/README.md` est architectural, pas de liste de dépendances/écrans à maintenir.
