## Why

La fiche patient actuelle empile verticalement six blocs (en-tête, infos, règlements,
plans & actes, documents) dans une seule colonne scrollable. L'identité occupe toute la
largeur en haut pour cinq lignes (espace perdu), les blocs sont éparpillés et imposent un
long défilement pour retrouver une information. Par ailleurs, aucun écran ne montre
**ce qui s'est passé** sur une fiche (création, modifications, plans, actes, documents) :
le praticien n'a pas de vue d'historique alors qu'une table `audit_log` existe déjà mais
reste globale, non structurée et jamais affichée.

## What Changes

- **Réorganisation de la fiche patient** en deux zones : une **colonne d'identité figée à
  gauche** (compacte : nom, contacts, date de naissance, montants clés Dû/Reste, bouton
  Modifier) et un **contenu en onglets à droite** : `Plans & actes`, `Documents`,
  `Règlements`, `Historique`. Le contexte patient reste visible quel que soit l'onglet.
- **Nouvel onglet « Historique »** : flux antichronologique des événements de la fiche,
  groupé par jour, avec icône et libellé lisible par type d'événement, **filtres par
  catégorie** (Fiche / Plans / Actes / Documents / Règlements) et, pour les mises à jour,
  **affichage des champs impactés (avant → après)**.
- **Enrichissement du journal d'audit** pour le rendre exploitable par patient :
  - ajout d'une colonne `patient_id` (nullable) et d'un `detail` **structuré (JSON)** sur
    `audit_log` ; **BREAKING** côté données interne uniquement (migration `SCHEMA_VERSION`
    v10 → v11, additive et rétrocompatible — les anciennes lignes restent lisibles, sans
    rattachement patient).
  - journalisation **systématique et enrichie** des événements : création de fiche, mise à
    jour de fiche (avec liste des champs modifiés et valeurs avant/après), création/édition/
    suppression de plan de traitement, ajout/édition/suppression d'acte, règlement d'acte,
    génération de document (avec type/modèle), génération de note d'honoraires, envoi email.
- **Aucune perte de fonctionnalité** : tous les blocs et actions existants (générer,
  imprimer, envoyer, régler, ajouter plan/acte, pagination, regroupement par catégorie des
  documents) sont conservés, redistribués dans les onglets.

## Capabilities

### New Capabilities

- `fiche-patient`: organisation et présentation de la page de détail d'un patient —
  colonne d'identité figée, navigation par onglets (Plans & actes, Documents, Règlements,
  Historique), conservation de toutes les actions existantes.
- `historique-patient`: journal d'audit par patient — enregistrement structuré des
  événements de la fiche et affichage chronologique filtrable avec détail des modifications
  (avant/après).

### Modified Capabilities

<!-- Aucune exigence des capabilities existantes (plans-de-traitement, referentiel-actes)
     n'est modifiée : leurs données et comportements sont inchangés, seul leur emplacement
     d'affichage est déplacé dans un onglet (couvert par la capability fiche-patient). -->

## Impact

- **Code** : `crm/app.py` (refonte de `show_patient_detail` et de ses helpers de blocs,
  ajout de la barre d'onglets et de la vue Historique), `crm/db.py` (migration v11 :
  colonnes `audit_log.patient_id` + `detail` JSON, index, anti-downgrade, snapshot
  pré-migration), `crm/repo.py` (`log_audit`/`list_audit` enrichis : `patient_id`, detail
  structuré, helpers de diff ; `update_patient` calcule les champs modifiés).
- **Données** : `SCHEMA_VERSION` passe à 11. Migration **additive** (colonnes nullables,
  `CREATE INDEX IF NOT EXISTS`) ; aucune donnée existante détruite ; les lignes
  `audit_log` antérieures restent valides (`patient_id` NULL, `detail` texte libre toléré).
- **UI** : desktop et web (même `crm/app.py`). Aucune dépendance nouvelle.
- **Hors périmètre** : moteur partagé `src/`, génération Word/Mailjet, schéma des plans/
  actes/documents (inchangés), export ou purge du journal.
