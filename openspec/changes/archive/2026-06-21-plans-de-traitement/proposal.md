## Why

Le cabinet ne peut pas suivre les soins d'un patient **dans le temps**. Aujourd'hui un
montant est saisi à la main sur un document ou un paiement, sans notion d'**acte réalisé**,
sans regroupement en **plan de soins**, et sans **paiement échelonné**. Un plan implantaire
(chirurgie → cicatrisation → couronne → contrôle) ou un simple **détartrage payé en deux
fois** ne sont pas modélisables.

Le côté fournisseur offre pourtant déjà exactement le bon patron : les **dépenses** gèrent
le règlement partiel daté, le reste à payer et le statut (`depenses` /
`depense_reglements`). Ce change apporte ce même mécanisme **côté patient**, pour des
actes — rattachés ou non à un plan — en réutilisant le **référentiel d'actes**
(`referentiel-actes`) pour pré-remplir les prix.

## What Changes

- **Nouvelle notion « acte réalisé » (`prestations`)** : un acte tarifé posé sur un
  patient. Son libellé et son prix sont **pré-remplis depuis le référentiel d'actes**
  (snapshot, modifiable). C'est l'unité qui porte **à la fois le dû et le paiement**.
- **Actes sans plan** : `plan_id` nullable. Un détartrage isolé est une prestation sans
  plan.
- **Plans de traitement** : un simple **regroupement nommé** d'actes d'un patient,
  **éditable à tout moment** (ajout / retrait / modification d'actes). **Sans cycle de vie
  ni statut** : pas de brouillon, pas de clôture. Le suivi se lit via le **statut de
  paiement de chaque acte** et les **barres de progression**.
- **Paiement partiel daté + reste + barre de progression** : chaque acte suit le modèle
  des dépenses — `montant` (dû), `montant_regle` (cumul), `reste`, `statut`
  (`en_attente` / `regle_partiellement` / `regle`) — avec un **historique de règlements
  datés** (`prestation_reglements`, calque de `depense_reglements`). **Règlement global réparti
  en cascade** : l'action « Régler » saisit **un montant reçu** réparti automatiquement sur les
  créances du plus ancien au plus récent (actes en partiel, puis notes) ; un **versement ciblé
  sur un acte** reste possible.
- **Pas de notion de « type »** : un acte de contrôle est simplement un **acte à montant
  nul** (de préférence une entrée « Consultation de contrôle » du référentiel à 0). Un acte
  à montant nul est **non facturable** (badge dérivé), n'apparaît pas dans les actes à
  régler et n'a pas de barre de progression. Chaque acte porte une **date** (réalisation, ou
  date prévue pour une visite à venir).
- **Champs optionnels par acte** : **dents concernées** (numéros FDI saisis en chips,
  séparés par virgule) et **note** libre — tous deux facultatifs.
- **`paiements` inchangée** : le visuel « **paiements en attente** » existant est
  **préservé** ; les actes apportent leur propre visibilité de créances.
- **Additif** : trois tables neuves, aucune touche aux tables ni aux flux existants.

## Capabilities

### New Capabilities

- `plans-de-traitement` : suivi des actes réalisés d'un patient (avec ou sans plan de
  regroupement), pré-remplis depuis le référentiel d'actes, avec paiement partiel daté,
  reste à payer et barres de progression — calqué sur le mécanisme des dépenses
  fournisseurs.

### Modified Capabilities

<!-- Aucune capability formalisée n'existe dans openspec/specs/. Les paiements et documents
     existants restent inchangés (pas de delta de capability existante). -->

## Impact

- **Schéma SQLite (`crm/db.py`)** : trois tables additives via `CREATE TABLE IF NOT
  EXISTS` — `plans_traitement`, `prestations`, `prestation_reglements`. Bump
  `SCHEMA_VERSION` (9 → 10, après `referentiel-actes`) + **snapshot pré-migration**.
  Aucune transformation de données.
- **`crm/repo.py`** : dataclasses `PlanTraitement`, `Prestation`, `PrestationReglement` +
  CRUD ; `add_prestation_reglement` **calque** `add_depense_reglement` (cumul +
  recalcul du statut) ; propriété `reste` sur `Prestation` ; totaux dérivés d'un plan
  (dû / encaissé / reste).
- **`crm/app.py`** : section « Plans & actes » dans la **fiche patient**
  (`show_patient_detail`) — actes isolés et plans repliables, **barres de progression** par
  acte et par plan. Un **composant « carte acte » réutilisable** (libellé, prix, date,
  dents, note) sert à la fois au dialogue d'ajout d'un acte isolé et au **composer de plan**
  (cartes empilées, un seul bouton « + Acte »). Le dialogue **« Régler »** combine le
  **récap** des actes non soldés (barres de progression) et le **versement en place**
  (calque de `_regler_depense`).
- **Consomme `referentiel-actes`** : `repo.list_actes` / `repo.get_acte` pour le
  pré-remplissage. Dépendance d'ordonnancement : `referentiel-actes` (v9) d'abord.
- **Moteur partagé (`src/`)** : **non modifié** ; pas de Word, pas de Mailjet.
- **Données** : 100 % additif ; `paiements`, `documents` et fichiers générés intacts.
