## Why

Aujourd'hui, générer une **note d'honoraires autonome** (mono-valeur, sans acte rattaché)
crée **systématiquement** une créance « note » (un `paiement` en_attente) du **montant exact
du document**, sans possibilité de choix. Or l'utilisateur a parfois besoin d'une note
**purement informative** (duplicata, courtoisie, situation déjà soldée) qui ne doit **pas**
alimenter le suivi financier, ou d'une note dont le **montant à recouvrer** diffère du montant
imprimé. Il faut donc rendre ce suivi **optionnel et paramétrable au moment de la génération**.

## What Changes

- À la génération d'une **note autonome mono-valeur**, le dialogue affiche une **case à cocher**
  « Tracer la note en attente (créance) », **cochée par défaut** (comportement actuel préservé).
- Quand la case est **cochée**, un **champ « Montant à suivre »** apparaît en dessous,
  **pré-rempli initialement avec le montant du document** ; ce montant est **indépendant** du
  montant imprimé sur la note (il ne pilote **que** la créance, pas le rendu du document).
- Quand la case est **décochée**, la note est générée normalement mais **aucune créance** n'est
  créée.
- La règle de gating de `generator.create_note_creance` est étendue : la créance n'est créée que
  si l'utilisateur l'a demandée (`tracer_creance`), et son montant peut être **surchargé**
  (`montant_creance`) indépendamment de `documents.montant`. L'idempotence (pas de double
  créance à la régénération) et le no-op pour les notes adossées à des actes restent inchangés.
- **Hors scope (réflexion reportée à une autre spec)** : le cas des **notes multi-lignes** (le dû
  y est déjà porté par les actes — un suivi optionnel y poserait un risque de double-comptage).

Aucun changement de schéma SQLite. Le défaut (case cochée, montant = montant du document) est
**rétro-compatible** : sans interaction, le comportement reste identique à l'existant.

## Capabilities

### New Capabilities
<!-- Aucune nouvelle capability : on étend une règle existante. -->

### Modified Capabilities
- `plans-de-traitement`: la règle **« Source unique du dû (pas de double-comptage) »** est
  assouplie pour les **notes autonomes** — la création de la créance « note » devient un **choix
  de l'utilisateur à la génération** (par défaut : créée), et son **montant devient surchargeable**
  indépendamment du montant affiché sur le document.

## Impact

- **Backend** (`crm/`) :
  - `crm/generator.py` — `create_note_creance` reçoit `track: bool` et
    `montant_override: float | None` ; le gating et le montant de la créance en tiennent compte.
  - `crm/routers/documents.py` — `DraftIn`/`GenerateIn` exposent `tracer_creance: bool = True` et
    `montant_creance: float | None = None` ; la route `generate` les transmet à `create_note_creance`.
- **Frontend** (`ui/`) :
  - `ui/src/screens/patient-detail/GenerateDialog.tsx` — case à cocher + champ montant pour la note
    autonome mono-valeur, et envoi des deux champs dans le corps de génération.
  - Régénérer le client TypeScript (`ui/src/api/schema.d.ts`, `types.ts`) depuis l'OpenAPI mis à jour.
- **Aucune** migration de schéma, **aucun** changement du moteur partagé `src/`.
