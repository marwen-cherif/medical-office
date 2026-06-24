## Why

Depuis la rédaction initiale de ce changement, deux capabilities ont été livrées :
**`referentiel-actes`** (catalogue d'actes tarifés) et **`plans-de-traitement`** (actes
réalisés — isolés ou rattachés à un plan — portant chacun libellé, montant, date, dents,
note et règlements partiels). Désormais, **le dû d'un patient est porté par ses actes**,
pas par les documents : `plans-de-traitement` a posé la règle **« source unique du dû »**
(générer un document ne crée *jamais* de paiement).

Or la **note d'honoraires** ne sait toujours pas **regrouper plusieurs actes** dans un
seul document : un document reste lié à **un** acte, **une** date et **un** montant
(`documents.acte_date`, `documents.montant`), et le moteur Word ne fait qu'une
substitution `<TAG>` → une valeur. Pour facturer en une note un détartrage du 01/05, deux
composites du 02/05 et une couronne du 05/06 déjà saisis comme actes, l'utilisateur doit
**ressaisir** chaque ligne à la main — alors que la donnée existe déjà sur la fiche.

La conception initiale prévoyait une **saisie manuelle ligne à ligne** avec un évaluateur
de formules par modèle. C'est aujourd'hui **redondant** (les montants vivent déjà sur les
actes) et **trop configurable** (un évaluateur d'expressions par modèle). Le besoin réel :
cliquer « Note d'honoraires », **choisir les actes** à facturer (isolés + plans),
**exploiter leurs données**, et laisser le modèle consommer un **jeu de variables standard
prédéfini** — sur le modèle d'un template transactionnel Mailjet (un contexte de variables
ouvert au modèle, que le modèle référence par leur nom).

## What Changes

- **Note d'honoraires multi-lignes générée depuis les actes** : le dialogue dédié
  « Note d'honoraires » propose les **actes du patient** (isolés + actes de plans),
  **regroupés** et **pré-cochés** ; l'utilisateur retient ceux à facturer. Les données de
  chaque acte (date, libellé, dents, montant, réglé, reste) alimentent une **ligne** de la
  note.
- **Ajout d'actes isolés depuis la note** : en complément des actes existants, possibilité
  d'**ajouter de nouveaux actes** via le **même formulaire que l'ajout d'acte** (référentiel,
  libellé, montant, date, dents avec odontogramme, note). Ces actes sont **créés comme actes
  isolés** — donc **suivis dans la dette** et **visibles dans l'onglet Actes/Plans** — puis
  inclus comme lignes de la note. (Remplace l'idée initiale de « lignes libres » non tracées,
  pour une UX plus simple et un suivi du dû cohérent.)
- **Contexte de variables standard prédéfini** (« à la Mailjet ») : un **contrat de
  balises documenté et fixe** — champs patient, **bloc de lignes** à colonnes connues
  (`<L_DATE>`, `<L_ACTE>`, `<L_DENTS>`, `<L_MONTANT>`, `<L_REGLE>`, `<L_RESTE>`) et
  **totaux** connus (`<TOTAL_DU>`, `<TOTAL_REGLE>`, `<RESTE_A_PAYER>`, `<NB_ACTES>`).
  Les modèles utilisent ces noms ; **aucune configuration de colonnes par modèle**.
- **Répétition dynamique de ligne** dans le moteur Word : une **ligne-modèle** de tableau
  marquée de balises `<L_*>` est **dupliquée** autant de fois qu'il y a de lignes, mise en
  forme préservée. Fonction **additive** : la logique de run-splitting existante
  (`_replace_in_para_elem`) n'est pas modifiée.
- **Totaux calculés en Python** (somme des montants, somme des réglés, reste, nombre de
  lignes) — **pas d'évaluateur de formules**, pas d'expressions configurables.
- **Aucun paiement, aucune créance dupliquée** : conforme à « source unique du dû » de
  `plans-de-traitement`. La note **référence** des actes ; le dû reste suivi sur les actes.
  Le total renseigne `documents.montant` uniquement comme **valeur d'affichage / email**,
  jamais comme une créance.
- **Aucune migration de schéma** : les lignes retenues sont sérialisées dans
  `documents.variables` (JSON déjà existant, clé réservée `__lignes__`).
- **Coexistence** : les modèles « simples » (mono-valeur) restent inchangés ; un modèle
  est « simple » ou « note multi-lignes » selon qu'il contient ou non des balises `<L_*>`.

## Capabilities

### New Capabilities

- `facturation-multi-lignes`: note d'honoraires regroupant **plusieurs actes** (isolés +
  plans, existants ou **créés à la volée comme actes isolés**) dans un seul document, via un
  **contexte de variables standard prédéfini** consommé par le modèle, une **répétition
  dynamique** de la ligne-modèle Word et des **totaux calculés** — sans paiement créé (le dû
  reste sur les actes) et sans migration de schéma.

### Modified Capabilities

<!-- Le bouton « Note d'honoraires — bouton dédié filtré par catégorie » défini dans
     `plans-de-traitement` n'est PAS rompu : il continue de filtrer les modèles par
     catégorie. Ce changement **enrichit** son dialogue de manière purement additive
     (étape de sélection d'actes + bloc de lignes) sans modifier l'exigence existante ;
     aucun delta MODIFIED n'est donc requis sur `plans-de-traitement`. La règle « source
     unique du dû » (aucun paiement à la génération) est respectée telle quelle. -->

## Impact

- **Moteur** (`src/doc_filler.py`) : ajout d'une fonction **additive** de duplication de
  ligne de tableau Word (clonage `w:tr` + remplissage de chaque copie via le **réutilisé**
  `_replace_in_para_elem`, sans toucher sa logique). `extract_placeholders` étendu pour
  distinguer balises de ligne (`L_*`) et balises document. Traversée des **cellules de
  tableau** (que `_fill_docx` n'explore pas aujourd'hui).
- **Pont CRM** (`crm/generator.py`) : construction du **contexte standard** depuis les
  actes sélectionnés (`repo.Prestation`), calcul des totaux, formatage français
  (`format_montant`), répétition des lignes à la génération, sérialisation sous `__lignes__`.
- **UI** (`crm/app.py`) : enrichissement du dialogue « Note d'honoraires » — sélection des
  actes (isolés + plans) **pré-cochés et regroupés**, **ajout d'actes isolés** via la carte
  d'acte réutilisée (référentiel + odontogramme), total recalculé en direct, prise en compte
  dans le cycle brouillon → génération → envoi (les nouveaux actes sont **créés** à
  l'enregistrement via `repo.create_prestation`).
- **Données** : **aucune migration** ; usage de `documents.variables` (JSON, clé
  `__lignes__`). `documents.montant` = total de la note (affichage/email), `documents.acte_date`
  = 1re date des lignes (nom de fichier stable). **Aucun paiement créé.**
- **Suppressions par rapport à la conception initiale** : plus d'évaluateur de formules
  (`src/formula.py` abandonné), plus de migration `template_fields.scope/expression`, plus
  de configuration de colonnes par modèle, plus de case « créer un paiement ».
- **Plateforme** : génération toujours dépendante de Word/COM (Windows uniquement).
