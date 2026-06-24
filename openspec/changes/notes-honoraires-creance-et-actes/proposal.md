## Why

Aujourd'hui une note d'honoraires ne porte **jamais** de dette : une note mono-valeur (montant
saisi à la main) ne crée **aucune** créance, et le montant d'une ligne de note **recopie
strictement** celui de l'acte. Le cabinet a besoin (1) qu'une note **non rattachée à un acte**
engendre une dette suivie sur la fiche patient, (2) de pouvoir **facturer sur la note un montant
différent** de celui enregistré sur l'acte, et (3) de **générer une note directement depuis la
page Actes/Plans** (sélection multiple ou acte unique) sans repasser par l'onglet Documents.

## What Changes

- **BREAKING** — Une note d'honoraires **autonome** (générée sans rattacher d'acte existant —
  typiquement une note mono-valeur) crée, **à la génération**, une **créance « note »**
  (`paiement` en_attente) rattachée au document, visible sur la page Actes/Plans et dans
  Finances. Cela lève la règle actuelle « générer une note ne crée jamais de paiement ».
- Le **montant de chaque ligne** d'une note multi-lignes devient **éditable** (valeur par défaut
  = montant de l'acte) et **purement d'affichage** : il peut différer du montant de l'acte
  **sans jamais modifier l'acte ni la dette** (l'acte reste la source du dû).
- Nouveau point d'entrée : sur la **page Actes/Plans**, sélectionner **un ou plusieurs actes**
  (isolés et/ou de plans) et **générer une note d'honoraires** pour la sélection.
- Nouveau point d'entrée : sur la **ligne d'un acte** (menu d'actions « ⋮ »), action
  **« Générer une note d'honoraires »** pour cet acte unique.
- **Inchangé (rappel)** : une note **adossée à des actes** (existants cochés ou ajoutés à la
  volée) ne crée **pas** de créance « note » — pas de double-comptage ; l'ajout d'acte à la
  volée continue de créer des **actes** suivis (`prestations`), jamais des paiements.
- **Cycle de vie** : la créance « note » est créée une fois à la génération (rattachée au
  document, sans doublon si la note est régénérée) puis **indépendante** — elle n'est ni
  resynchronisée ni supprimée automatiquement avec la note ; l'utilisateur la gère à la main
  (encaisser / annuler).

## Capabilities

### New Capabilities

- (aucune) — le changement fait évoluer des capabilities existantes, sans en introduire de
  nouvelle.

### Modified Capabilities

- `plans-de-traitement` : l'exigence **« Source unique du dû (pas de double-comptage) »** devient
  **conditionnelle** — générer une note **adossée à des actes** ne crée pas de paiement, mais
  générer une note **autonome** (sans acte rattaché) crée une **créance « note »**. (La règle
  redondante de `facturation-multi-lignes` est retirée et centralisée ici.)
- `facturation-multi-lignes` : le **montant de ligne** devient un **défaut modifiable** distinct
  du montant de l'acte (affichage seul, sans effet sur la dette) ; ajout des **points d'entrée**
  de génération de note depuis une **sélection d'actes** (page Actes/Plans, action sur une ligne
  d'acte) ; retrait de la règle « Aucun paiement créé à la génération » (remplacée par la règle
  conditionnelle de `plans-de-traitement`).

## Impact

- **Backend (`crm/`)** : `generator.py` (créer une créance « note » à la génération d'une note
  autonome ; porter un montant de ligne *override* dans la clé `__lignes__`), `routers/
  documents.py` (formulaire / brouillon / génération : montant éditable par ligne, distinction
  note autonome ↔ adossée), `routers/clinical.py` (pré-sélection d'actes pour la génération).
  Réutilise `repo.create_paiement` et le lien existant `paiements.document_id` —
  **aucune migration de schéma**.
- **Frontend (`ui/`)** : `GenerateDialog.tsx` (montant éditable par ligne), `PlansActesTab.tsx`
  (mode sélection multiple + bouton « Générer une note », menu « ⋮ » par acte), hooks
  `documents.ts` / `clinical.ts`, types régénérés (`api/schema.d.ts`, `api/types.ts`).
- **Données** : pas de migration destructive ; réutilise la table `paiements` (avec
  `document_id`) et la clé réservée `__lignes__` de `documents.variables`. Le total de la note
  reste une valeur d'**affichage** (`documents.montant`), jamais une créance pour une note
  adossée à des actes.
- **Hors périmètre** : moteur `src/` (Word/Mailjet), contrat de balises `<L_*>` des modèles
  `.docx` (inchangé).
