## Context

L'odontogramme React de **saisie** (`ui/src/components/common/Odontogramme.tsx`) est une grille
de boutons numérotés, **contrôlée** (`value: string[]` / `onChange`), avec bascule Adulte/Enfant
et numéros FDI affichés **en permanence** — propriété essentielle à la saisie rapide. Il est
consommé par `ActeCard` (dans `PrestationDialog`, `PlanDialog`, et la saisie d'actes de
`GenerateDialog`). Les dents sont persistées sous forme de **chaîne FDI séparée par des
virgules** dans `prestations.dents` ; `dentureFor(date_naissance)` choisit la denture par
défaut.

On veut **ajouter** une **lecture clinique synthétique** : un schéma dentaire anatomique
colorisé selon l'état (réalisé / planifié), en **lecture seule**, sur la fiche patient. La
librairie **`react-odontogram`** (composant `Odontogram`, SVG, notation FDI) convient pour ce
rendu. Limite connue : elle **n'affiche le numéro de dent qu'au survol** (infobulle), sans option
d'étiquette permanente. C'est **acceptable pour une vue de consultation** colorisée, mais **pas**
pour la saisie — d'où l'**approche hybride** : la grille numérotée reste la saisie, la librairie
ne sert qu'à la visualisation. Voir `proposal.md` (motivation) et `specs/selection-dents/spec.md`
(exigences).

Propriétés utiles de la librairie (vérifiées sur la v0.5.6 installée) : `defaultSelected`,
`onChange`, `notation="FDI"`, `maxTeeth`, `theme`/`colors`, **`teethConditions`** (colorisation
par groupe : `{ label, teeth, fillColor, outlineColor }`), **`readOnly`**, **`showLabels`**
(légende), `showTooltip`, `tooltip.content` (renderer d'infobulle personnalisable). Import requis :
`react-odontogram/style.css`.

**Comportement réel des identifiants et de la denture** (issu de l'inspection du bundle + de la
story `zBaby.stories.tsx`) : chaque dent porte l'identifiant `` `teeth-${quadrant}${position}` ``
avec **quadrant ∈ {1,2,3,4}** et **position ∈ {1..maxTeeth}**. `maxTeeth=8` ⇒ dentition
**permanente** numérotée exactement comme la FDI (`teeth-26` = FDI 26). `maxTeeth=5` ⇒ dentition
**temporaire** (20 dents de lait), mais **numérotée avec les quadrants permanents** (`teeth-11`…
`teeth-15`, `teeth-21`…) — **pas** avec la FDI internationale des dents de lait (51–85). Les clés
de `teethConditions[].teeth` et de `defaultSelected` doivent donc être des `"teeth-<…>"`, et un
**mapping** est nécessaire entre la FDI de l'application (51–85) et les positions de la librairie.

## Goals / Non-Goals

**Goals :**
- Ajouter un **odontogramme clinique en lecture seule** colorisant les dents réalisées /
  planifiées, alimenté par les données `clinical` déjà chargées.
- **Mettre en évidence** les dents d'un acte sur le schéma au **survol** de sa ligne dans la
  liste.
- **Ne rien changer** à la saisie : `Odontogramme.tsx` et ses quatre points d'appel restent
  intacts (numéros permanents préservés).
- **Aucun** changement backend, **aucune** migration ; rendu identique desktop (Tauri) et web.

**Non-Goals :**
- Remplacer la grille de saisie par la librairie (numéros permanents indispensables → exclu).
- Rendre l'odontogramme clinique éditable.
- Étiquettes FDI permanentes sur la vue clinique (la librairie ne les supporte pas ; numéro au
  survol accepté pour cette vue).
- Notations Universal/Palmer, vue 3D, tout changement de schéma SQLite ou d'API.

## Decisions

### 1. Approche hybride : grille pour la saisie, librairie pour la visualisation

La grille numérotée existante reste **l'unique moyen de saisie** (numéros permanents). La
librairie `react-odontogram` est introduite **uniquement** dans un **nouveau** composant de
consultation. Aucune réconciliation contrôlé/non-contrôlé n'est nécessaire puisque la vue est en
**lecture seule** (pas de remontée d'état).
- **Alternative rejetée** : remplacer la grille par la librairie. Rejeté car la librairie
  n'affiche pas les numéros en permanence — régression directe pour la saisie.
- **Alternative rejetée** : superposer une couche d'étiquettes FDI maison sur le SVG de la
  librairie pour la saisie. Rejeté : fragile (dépend de la structure interne du SVG), coût
  disproportionné.

### 2. Composant `OdontogrammeClinique.tsx` (lecture seule), denture adaptée à l'âge

Nouveau composant `ui/src/components/common/OdontogrammeClinique.tsx` : `Odontogram` en
`readOnly`, `showTooltip`, `showLabels` (légende), `notation="FDI"`. La **denture suit l'âge** du
patient (réutilise `dentureFor(date_naissance)`) : `maxTeeth=8` pour un **adulte** (32 dents
permanentes), `maxTeeth=5` pour un **enfant** (20 dents de lait). L'**infobulle est
personnalisée** (`tooltip.content`) pour afficher le **vrai numéro FDI** : identité en adulte,
reconversion position → FDI de lait en enfant (cf. décision 3). Il reçoit les **groupes de
conditions** + la **liste hors-schéma** déjà calculés et **n'exploite aucun `onChange`**.

### 3. Dérivation `teethConditions` + mapping FDI ↔ librairie

Construction à partir de `clinical.data` (déjà chargé par `useClinical`, pas de nouvelle
requête) : parcourir `isoles` + `plans[].prestations`, éclater `prestation.dents` via
`parseDents`, et classer chaque dent en deux états :
- **Réalisé** (`fillColor` plein, palette `navy`/`teal` de l'app) ;
- **Planifié** (couleur secondaire / `outlineColor`).

**Prédicat retenu** (défaut) : une dent est **réalisée** si au moins un acte **daté**
(`date_acte` non nul) la porte ; sinon **planifiée**. En cas de présence dans les deux,
**réalisé l'emporte**. Logique **centralisée** dans une seule fonction, donc ajustable d'un seul
endroit.

**Mapping FDI ↔ identifiant librairie** (helpers dédiés, testables) selon la denture :
- **Adulte** : FDI permanente `^[1-4][1-8]$` → `"teeth-<fdi>"` (identité). Sinon (dent de lait,
  jeton non-FDI) ⇒ **hors-schéma**.
- **Enfant** : FDI de lait `^[5-8][1-5]$` → `"teeth-<quadrant-4><position>"` (ex. **55 →
  `teeth-15`**, **71 → `teeth-31`**). Sinon (dent permanente, jeton non-FDI) ⇒ **hors-schéma**.
- **Infobulle** (sens inverse) : en enfant, `teeth-15` → FDI « 55 » (`quadrant+4`) ; en adulte,
  identité.

Les dents **hors-schéma** ne sont pas perdues : elles sont **collectées par état** et renvoyées
au composant pour un **rendu texte** sous le schéma (filet de sécurité denture mixte / jetons
inattendus). `teethConditions[].teeth` reçoit les ids `"teeth-…"` mappés ; les dents en double
sont dédupliquées (réalisé prioritaire).

### 4. Placement et rafraîchissement

Section dédiée en tête de l'onglet **Plans & actes** (`PlansActesTab.tsx`), au-dessus des actes
isolés. La vue lit `clinical.data` : grâce à l'invalidation TanStack Query déjà en place
(`invalidatePatient`), elle se **rafraîchit automatiquement** après toute mutation d'acte. Gérer
le cas « aucune dent » (schéma neutre, sans condition).

### 5. Dépendance, feuille de style — spike réalisé

Ajout de `react-odontogram@0.5.6` (version **épinglée** via `--save-exact`) dans
`ui/package.json` ; import unique de `react-odontogram/style.css`. **Spike effectué** (lecture
des types `dist/index.d.ts`, du bundle et de la story `zBaby.stories.tsx`) : (a) peer
`react >=17` ⇒ **React 19 compatible, pas d'`overrides`** ; (b) `teethConditions[].teeth` et
`defaultSelected` attendent des ids **`"teeth-<…>"`** ; (c) la denture temporaire s'obtient via
**`maxTeeth=5`** mais reste numérotée en quadrants 1–4 ⇒ **mapping requis** (décision 3).

### 6. Survol d'un acte → mise en évidence des dents

L'état de **survol** est porté par `PlansActesTab` (`hoverFdis: string[] | null`) : chaque
`PrestationRow` émet `onHover(parseDents(pres.dents))` sur `mouseEnter` et `onHover(null)` sur
`mouseLeave`. `OdontogrammeClinique` reçoit `highlightFdis` et ajoute un **groupe
`teethConditions` supplémentaire en dernier** (couleur ambre) : comme la librairie applique les
conditions via une `Map` (dernier groupe gagnant), les dents survolées **écrasent**
temporairement leur couleur d'état. Les dents survolées **hors-schéma** sont surlignées dans la
liste texte. La mise en évidence est **transitoire** (aucun remontage, aucune donnée modifiée).
La légende native (`showLabels`) est **désactivée** au profit d'une **légende maison** pour
éviter qu'un libellé « Survolé » n'apparaisse/disparaisse dans la légende au gré du survol.

### 7. En-tête (actions + schéma) épinglé au défilement (sticky)

Le bloc [barre d'actions + `OdontogrammeClinique`] est enveloppé dans un conteneur
`sticky top-0 z-20` (fond opaque `bg-bg`) au sein du **conteneur défilant** de l'app
(`<main overflow-auto>` de `Shell`). La chaîne d'ancêtres (flex + Radix `Tabs`) n'introduit ni
`overflow` ni `transform`, donc le sticky s'accroche bien à `<main>`. Pour éviter qu'un schéma
trop haut ne **dépasse la hauteur du viewport** (ce qui empêcherait d'atteindre la liste), la
largeur du schéma est **bornée** (`max-w-sm`), le SVG étant scalable. Compromis : l'en-tête
épinglé réduit l'espace de défilement ; acceptable car c'est l'objectif (schéma toujours
visible).

## Risks / Trade-offs

- **Denture mixte non représentable en un seul schéma** (la librairie n'affiche qu'une denture à
  la fois) → on rend la denture de l'âge et on **liste en texte** les dents de l'autre denture
  (filet de sécurité, décision 3) ; aucune perte d'information.
- **Numéro visible seulement au survol** sur la vue clinique → accepté ; légende couleur + survol
  (infobulle corrigée affichant la vraie FDI) suffisent à l'identification.
- **Maturité de la librairie (version 0.x)** → version épinglée ; usage **circonscrit** à un seul
  composant de consultation, donc remplacement futur peu coûteux et sans impact sur la saisie.
- **Prédicat réalisé / planifié imparfait** (si les dates d'acte sont peu renseignées) → logique
  centralisée, ajustable sans toucher au reste.
- **Couplage au schéma interne de la librairie** (ids `teeth-<quadrant><position>`) → encapsulé
  dans des helpers de mapping dédiés et testables ; si la librairie change, un seul endroit à
  adapter.

## Migration Plan

Changement **purement additif** côté UI, **sans migration de données**.
1. Ajouter la dépendance `react-odontogram` + import CSS ; spike de vérification.
2. Créer `OdontogrammeClinique.tsx` + la fonction de dérivation des `teethConditions`.
3. Insérer la section visualisation dans `PlansActesTab`.
4. Recette manuelle : colorisation réalisé/planifié, légende, survol du numéro, cas « aucune
   dent », rafraîchissement après mutation — **en desktop (Tauri) et en web**. Vérifier que la
   **saisie est inchangée**.
5. **Rollback** : retirer le composant et la dépendance (`git revert`) ; aucune donnée affectée,
   aucun schéma touché, saisie intacte par construction.

## Open Questions

- **Prédicat « réalisé » vs « planifié »** : se baser sur la **présence d'une date d'acte**
  (défaut proposé) ou sur l'**appartenance à un plan de traitement** ? À confirmer selon la façon
  dont le cabinet saisit les dates.

_(Résolu au spike : React 19 compatible ; dents de lait affichables via `maxTeeth=5` + mapping
FDI 51–85 → positions librairie ; choix denture adaptée à l'âge + liste texte hors-schéma.)_
