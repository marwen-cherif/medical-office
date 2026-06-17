## Why

Aujourd'hui, un document est lié à **un seul acte, une seule date et un seul
montant** (`documents.acte_date`, `documents.montant`), et le moteur Word ne sait
faire qu'une substitution simple `<TAG>` → une valeur. Impossible donc d'émettre une
**note d'honoraires unique regroupant plusieurs visites** (ex. 01/05, 02/05, 05/05,
01/06) avec, pour chacune, son acte et son montant, puis un total. Le cabinet doit
aujourd'hui produire un document par date, ce qui multiplie les envois et empêche une
facturation récapitulative pourtant courante.

## What Changes

- Introduction d'un **nouveau type de template « tableau »** : en plus des templates
  mono-valeur existants, un template peut déclarer un **bloc de lignes répétables**
  (un tableau d'objets) dont chaque ligne porte des colonnes typées (ex. `date`,
  `acte`, `quantite`, `prix_unitaire`, `montant`).
- **Répétition dynamique de ligne** dans le moteur de remplissage Word : une
  **ligne-modèle** marquée de balises de ligne (`<L_DATE>`, `<L_ACTE>`,
  `<L_MONTANT>`, …) est **dupliquée** autant de fois qu'il y a de lignes saisies,
  en préservant la mise en forme. Fonction **additive** : la logique de
  run-splitting existante (`_replace_in_para_elem`) n'est pas modifiée.
- **Valeurs calculées bornées** (pas de moteur Excel libre, pas d'`eval`) :
  - colonnes calculées **par ligne** via arithmétique (`+ - * /`, parenthèses) sur
    les colonnes de la ligne — ex. `montant = quantite * prix_unitaire` ;
  - **agrégats au niveau document** sur une colonne : `SUM`, `COUNT`, `AVG`, `MIN`,
    `MAX` — ex. `<TOTAL> = SUM(montant)`.
- **Saisie ligne à ligne** dans la fiche patient : ajout / suppression /
  réordonnancement de lignes, avec calcul du total en direct.
- **Intégration paiements** : le total calculé alimente `document.montant`, donc le
  suivi des impayés du patient — identique au comportement d'un document mono-date.
- **Coexistence** : les templates mono-date actuels restent inchangés ; un template
  est « tableau » ou « simple ». Aucune note déjà générée n'est affectée.
- **Aucune migration lourde de schéma** : les lignes saisies et les valeurs calculées
  sont sérialisées dans la colonne `documents.variables` (JSON) déjà existante.

## Capabilities

### New Capabilities

- `facturation-multi-lignes`: type de template « tableau » regroupant plusieurs lignes
  (date/acte/montant…) dans un même document, avec répétition dynamique de la
  ligne-modèle Word et valeurs calculées bornées (colonnes par ligne + agrégats
  document), saisie ligne à ligne et report du total sur le suivi des paiements.

### Modified Capabilities

<!-- Aucune capability formalisée n'existe encore dans openspec/specs/. Le comportement
     mono-date actuel reste inchangé : pas de delta de capability existante. -->

## Impact

- **Code moteur** (`src/doc_filler.py`) : ajout d'une fonction additive de duplication
  de ligne de tableau Word (sans toucher `_replace_in_para_elem`) et détection des
  balises de ligne. `extract_placeholders` étendu pour distinguer balises de ligne et
  balises document.
- **Pont CRM** (`crm/generator.py`) : construction des remplacements pour les lignes,
  exécution de l'évaluateur de calculs bornés, calcul du total, report sur
  `document.montant`. Sérialisation des lignes dans `variables`.
- **Configuration template** (`crm/templates.py`, table `template_fields`) : déclaration
  des colonnes de ligne et des champs calculés d'un template « tableau » (de manière
  additive, expand-only).
- **UI** (`crm/app.py`) : éditeur de lignes (ajout/suppression/réordonnancement) dans la
  fiche patient, total en direct, prise en compte du nouveau type côté brouillon /
  génération / envoi.
- **Nouveau module** : un évaluateur d'expressions borné (parser sûr, sans `eval`) pour
  les colonnes calculées et les agrégats.
- **Données** : aucune migration destructive ; usage de `documents.variables` (JSON).
  Le total renseigne `documents.montant` et crée/alimente un paiement comme aujourd'hui.
- **Plateforme** : génération toujours dépendante de Word/COM (Windows uniquement).
