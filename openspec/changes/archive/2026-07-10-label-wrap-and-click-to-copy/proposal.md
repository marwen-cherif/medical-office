## Why

Actuellement, les étiquettes (tags), libellés (labels) et libellés de menus peuvent parfois subir des retours à la ligne indésirables, ce qui nuit à la lisibilité et à l'esthétique générale de l'interface utilisateur. De plus, il n'existe pas de mécanisme standard et rapide pour copier les informations affichées à l'écran (comme les adresses email, les numéros de téléphone, les adresses postales) sur les fiches des patients et des prestataires, forçant l'utilisateur à faire des sélections manuelles fastidieuses.

## What Changes

- Ajout de la classe de non-retour à la ligne (`whitespace-nowrap`) sur les composants de base : `Badge`, `Label`, et `DropdownMenuLabel`.
- Création d'un nouveau composant réutilisable (atome) `ClickToCopy` pour copier facilement n'importe quel texte au clic.
- Intégration du composant `ClickToCopy` sur les fiches de détails des patients et prestataires pour toutes les données copiables (email, téléphone, adresse, etc.).
- Ajout d'une notification visuelle de confirmation de copie (icône temporaire et toast subtil).

## Capabilities

### New Capabilities
- `click-to-copy`: Fournir un composant réutilisable pour copier des données textuelles dans le presse-papiers avec retour visuel immédiat (icône de succès) et accessibilité clavier.

### Modified Capabilities
- `fiche-patient`: Les informations clés du patient (email, téléphone, adresse, date de naissance) SHALL être copiables d'un simple clic et présentées sans retour à la ligne intempestif.
- `fiche-prestataire`: Les informations clés du prestataire (email, téléphone, adresse) SHALL être copiables d'un simple clic et présentées sans retour à la ligne intempestif.

## Impact

- `apps/web/src/components/ui/badge.tsx`
- `apps/web/src/components/ui/label.tsx`
- `apps/web/src/components/ui/dropdown-menu.tsx`
- `apps/web/src/components/ui/click-to-copy.tsx` [NEW]
- `apps/web/src/screens/PatientDetail.tsx` (IdRow)
- `apps/web/src/screens/PrestataireDetail.tsx` (Row)
