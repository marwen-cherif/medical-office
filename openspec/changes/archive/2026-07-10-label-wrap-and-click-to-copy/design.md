## Context

Les éléments textuels courts de type badges, libellés (labels) et options de menus ne doivent pas subir de retour à la ligne pour conserver l'esthétique et la structure de l'interface (notamment dans les tableaux et les formulaires). De plus, l'accès rapide aux données affichées (coordonnées des patients/prestataires) est une fonctionnalité de confort importante pour les utilisateurs du cabinet médical.

## Goals / Non-Goals

**Goals:**
- Garantir le non-retour à la ligne pour `Badge`, `Label` et `DropdownMenuLabel` en ajoutant la classe CSS `whitespace-nowrap`.
- Créer un composant réutilisable et premium `ClickToCopy` pour copier n'importe quel texte par simple clic ou via clavier.
- Intégrer ce composant dans les volets de détails des patients (`PatientDetail.tsx`) et prestataires (`PrestataireDetail.tsx`).
- Fournir un retour visuel animé et persistant de 2 secondes (icône checkmark) plus un toast informatif.

**Non-Goals:**
- Modifier les formulaires d'édition ou les champs de saisie pour ajouter la copie.
- Ajouter la copie sur des champs non textuels ou complexes (comme les montants monétaires déjà formatés).

## Decisions

### 1. Composant `ClickToCopy` et transition visuelle
- **Décision :** Créer le composant `ClickToCopy` dans `apps/web/src/components/ui/click-to-copy.tsx` sous forme d'un conteneur interactif avec un état local `copied` géré via `useState`.
- **Raisonnement :** L'état local permet de contrôler l'icône affichée (`Copy` vs `Check`) et de réinitialiser l'icône après un délai de 2000 ms via `setTimeout`. L'utilisation d'un bouton invisible ou d'un conteneur avec `role="button"` et `tabIndex={0}` assure la navigabilité au clavier.
- **Alternatives :** Utiliser une bibliothèque tierce de copie. Écarté car `navigator.clipboard.writeText` est natif, performant, et très simple à implémenter sans ajouter de dépendance.

### 2. Intégration dans `IdRow` et `Row`
- **Décision :** Mettre à jour les fonctions utilitaires locales de rendu de lignes dans `PatientDetail.tsx` (`IdRow`) et `PrestataireDetail.tsx` (`Row`) pour envelopper automatiquement la valeur affichée dans `ClickToCopy`.
- **Raisonnement :** Cela centralise l'affichage sans dupliquer le code pour chaque champ individuel. Si la valeur est absente ou vaut « — », le composant ne sera pas interactif.

### 3. Modifications des composants UI atomiques
- **Décision :** Modifier directement les définitions de classe CSS Tailwind dans `badge.tsx`, `label.tsx`, et `dropdown-menu.tsx`.
- **Raisonnement :** Ces composants atomiques doivent par défaut empêcher le retour à la ligne pour respecter la charte de l'application.

## Risks / Trade-offs

- **[Risk]** Le non-retour à la ligne (`whitespace-nowrap`) sur les labels longs pourrait provoquer un débordement horizontal ou tronquer le texte si le conteneur est trop étroit.
  - **Mitigation :** Les étiquettes et libellés du cabinet médical sont des textes courts maîtrisés. Pour les adresses longues, le conteneur principal dispose d'un espace suffisant ou gère le scroll/tronquage.
