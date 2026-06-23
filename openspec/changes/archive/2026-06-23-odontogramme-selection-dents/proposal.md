## Why

La saisie des **dents concernées** par un acte se fait aujourd'hui dans un seul champ
texte « Dents (FDI) » : il faut taper le numéro puis **valider** par Entrée (ou le bouton
« + ») pour créer un chip (`_acte_card`, `crm/app.py`). Deux frictions au fauteuil :

1. **Saisie vocale impraticable** : le praticien dicte « 26 27 28 » (mains occupées, gants),
   mais les dents ne deviennent des chips que si l'on valide explicitement — la dictée
   remplit le champ sans jamais le confirmer.
2. **Aucun repère visuel** : il faut connaître la numérotation FDI de tête ; on ne voit pas
   sur une vraie arcade quelles dents sont déjà retenues, ni distinguer une **denture
   adulte** (permanentes) d'une **denture enfant** (temporaires).

Il n'existe aucune librairie d'odontogramme exploitable en Python/Flet (l'écosystème est
JS web ou Flutter) ; le besoin se couvre par un **composant natif Flet** réutilisable.

## What Changes

- **Saisie continue (compatible voix)** : le champ « Dents (FDI) » **alimente les chips au
  fil de la frappe/dictée**, dès qu'un numéro est terminé par un séparateur (espace,
  virgule, point-virgule), **sans Entrée ni bouton « + »**. Entrée, « + » et la perte de
  focus restent des déclencheurs valides (compatibilité + dernier numéro dicté non perdu).
- **Odontogramme cliquable** sous le champ : un **schéma dentaire natif Flet** en
  disposition FDI (croix : maxillaire en haut / mandibulaire en bas, **droite** patient à
  gauche de l'écran / **gauche** à droite). Un clic sur une dent **bascule** sa sélection.
- **Bascule denture adulte / enfant** : adulte = dents **permanentes** (FDI 11–48), enfant
  = dents **temporaires** (FDI 51–85). Le composant choisit une denture par défaut selon
  l'âge du patient quand la date de naissance est connue, et reste **basculable** à la main.
- **Synchronisation bidirectionnelle** champ ↔ chips ↔ odontogramme : une dent retenue,
  quelle que soit sa source, est **surlignée** sur le schéma **et** présente en chip ; la
  retirer (chip, re-clic, édition du champ) la **désélectionne partout**.
- **Composant réutilisable** intégré dans la **carte d'acte** (`_acte_card`) : il bénéficie
  donc à la fois au **dialogue d'acte isolé** et au **composer de plan de traitement**.
- **Aucune dépendance nouvelle, aucun changement de build, aucune migration** : la
  persistance reste `prestations.dents` en chaîne « 26, 27 » ; la validation FDI demeure
  **facultative et non bloquante** (la saisie libre type « 26 (MOD) » reste tolérée).

## Capabilities

### New Capabilities

- `selection-dents`: sélection des dents concernées par un acte via une **saisie continue
  compatible dictée vocale** et un **odontogramme cliquable** (denture adulte/enfant en
  notation FDI), synchronisés de façon bidirectionnelle, sans modifier le format de
  persistance (chips → chaîne « 26, 27 ») ni la validation non bloquante existante.

### Modified Capabilities

<!-- L'exigence « Dents concernées en notation FDI (optionnel) » de `plans-de-traitement`
     n'est PAS rompue : ses garanties (chips, persistance « 26, 27 », champ facultatif,
     validation FDI non bloquante) restent vraies à l'identique. Ce changement **enrichit
     de façon purement additive** le mécanisme de saisie (commit continu + odontogramme)
     sans réécrire l'exigence ni invalider ses scénarios (« 26 puis 27 → 26, 27 », « champ
     vide → acte valide »). Aucun delta MODIFIED n'est donc requis sur
     `plans-de-traitement`. -->

## Impact

- **UI** (`crm/app.py`) : la carte d'acte `_acte_card` gagne (a) un champ à **commit
  continu** (`on_change` + `on_blur`, en plus de `on_submit`/« + »), (b) un **composant
  odontogramme** réutilisable rendu sous le champ, (c) la **synchronisation** chips ↔
  schéma. Sélection par défaut adulte/enfant dérivée de l'âge si la naissance est connue.
- **Logique FDI** (`crm/repo.py`) : ajout de **helpers purs** (table des dents permanentes
  11–48 et temporaires 51–85, quadrant/validité d'un numéro) servant l'odontogramme et la
  classification adulte/enfant. `normalize_dents` (format de persistance) **inchangé**.
- **Données** : **aucune migration** ; `prestations.dents` conserve le format « 26, 27 ».
- **Parité desktop / web** : composant 100 % Flet (aucun widget natif), donc rendu et clics
  **identiques** en fenêtre desktop et en mode web (même `crm/app.py`).
- **Voix** : repose sur la **dictée du système d'exploitation** qui écrit dans le champ
  focalisé ; aucune API micro ni dépendance ajoutée.
- **Aucune suppression** de fonctionnalité : le champ texte, Entrée et « + » subsistent.
