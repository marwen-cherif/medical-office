# click-to-copy Specification

## Purpose
TBD - created by archiving change label-wrap-and-click-to-copy. Update Purpose after archive.
## Requirements
### Requirement: Composant ClickToCopy réutilisable

Le système SHALL fournir un composant réutilisable nommé `ClickToCopy` pour encapsuler et copier des données textuelles.
Le composant SHALL afficher la valeur textuelle sous forme d'un élément cliquable et focalisable par le clavier.
Au survol (hover) ou lors du focus, le composant SHALL faire apparaître discrètement une icône de copie.
Lors du clic sur le composant, la valeur textuelle SHALL être copiée dans le presse-papiers du système.
Après une copie réussie, l'icône de copie SHALL être remplacée temporairement par une icône de validation (crochet/check) pendant 2 secondes.
Le composant SHALL forcer le non-retour à la ligne (`whitespace-nowrap`) de la valeur affichée.

#### Scenario: Copie au clic avec retour visuel
- **WHEN** l'utilisateur clique sur le texte ou le bouton de copie du composant `ClickToCopy`
- **THEN** la valeur textuelle associée est copiée dans le presse-papiers
- **AND** l'icône de copie se transforme temporairement en icône de validation (check)
- **AND** un message de confirmation "Copié !" s'affiche via un toast

#### Scenario: Copie via interaction clavier
- **WHEN** l'utilisateur navigue au clavier sur le composant `ClickToCopy` et appuie sur Entrée ou Espace
- **THEN** la valeur textuelle associée est copiée dans le presse-papiers
- **AND** le retour visuel (changement d'icône et toast) est déclenché de la même façon

