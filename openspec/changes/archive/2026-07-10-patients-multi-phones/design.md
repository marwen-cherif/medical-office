## Context

L'application de cabinet médical utilise un monorepo avec une interface React et un backend FastAPI/SQLite. Actuellement, la table `patients` ne possède qu'une colonne unique `telephone` (TEXT) stockant un seul numéro de téléphone par patient. 
Il est nécessaire de faire évoluer le modèle pour gérer plusieurs numéros (patients et proches), avec pour chacun une relation (ex: conjoint, père, mère) et un indicateur de compatibilité WhatsApp. Cette information sera ensuite exploitée pour router intelligemment les messages WhatsApp.

## Goals / Non-Goals

**Goals:**
- Permettre d'enregistrer plusieurs numéros de téléphone par patient, chacun qualifié par une relation (Lui-même, conjoint, père, mère, enfant, autre) et un indicateur WhatsApp.
- Assurer une saisie ergonomique avec sélection de pays (drapeau, indicatif téléphonique).
- Proposer le choix du numéro destinataire lors de l'envoi WhatsApp si plusieurs numéros compatibles sont présents.
- Assurer une rétrocompatibilité complète (conservation des données existantes, non-régression sur le fonctionnement des documents existants).

**Non-Goals:**
- Supprimer ou renommer la colonne `patients.telephone` (qui doit être conservée et synchronisée pour rétrocompatibilité).
- Gérer un historique d'envoi WhatsApp par numéro de téléphone (le statut d'envoi reste lié aux documents).

## Decisions

### 1. Modèle de données et table SQLite `patient_phones`
Nous créons une table dédiée pour stocker la liste des téléphones :
```sql
CREATE TABLE IF NOT EXISTS patient_phones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id      INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    telephone       TEXT NOT NULL,
    relation        TEXT NOT NULL,
    is_whatsapp     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
```
- **Rétrocompatibilité** : La colonne `patients.telephone` est conservée. À chaque création ou modification de patient, la valeur de `patients.telephone` est automatiquement mise à jour avec le numéro principal (celui qui a la relation "Lui-même", ou à défaut le premier numéro de la liste). Cela garantit que toute requête ou partie de code existante (comme l'affichage dans la liste des patients) continue de fonctionner sans modification.
- **Migration v15** : Une migration insère automatiquement les numéros non nuls de `patients.telephone` dans `patient_phones` avec la relation 'Lui-même' et `is_whatsapp = 1`.

### 2. Extension du Backend FastAPI et repo Python
- La classe `Patient` de `repo.py` gagne un champ `telephones: list[PatientPhone]`.
- Les fonctions `get_patient`, `create_patient` et `update_patient` intègrent la lecture et l'écriture dans la table `patient_phones`. L'écriture supprime les anciennes lignes téléphoniques pour les réinsérer (approche simple et sûre).
- L'endpoint `POST /documents/{document_id}/send-whatsapp` accepte désormais un corps optionnel :
  ```json
  { "telephone": "+21655777766" }
  ```
  S'il est fourni, le document est envoyé à ce numéro ; sinon, l'API utilise par défaut `patient.telephone`.

### 3. Saisie téléphonique et sélection du pays
- Nous implémentons une liste statique des principaux pays (Tunisie, France, Algérie, Maroc, etc.) avec leur indicatif et drapeau (émoji).
- Dans le formulaire React `PatientFormDialog.tsx`, nous offrons une saisie multi-lignes où l'utilisateur peut ajouter et supprimer des lignes. Chaque ligne affiche :
  1. Un sélecteur de relation (suggestions sous forme de dropdown : Lui-même, Le conjoint, Père, Mère, L'enfant, Autres) ou saisie libre.
  2. Le champ téléphone avec sélecteur de pays / indicatif.
  3. Un commutateur (Switch) pour activer/désactiver WhatsApp.
- Lors du chargement du formulaire, les numéros au format E.164 sont analysés pour extraire l'indicatif et pré-sélectionner le pays correspondant.
- Lors de la soumission, les numéros sont recomposés au format E.164 (`+indicatif` + `numéro`).

### 4. Dialogue de sélection lors de l'envoi WhatsApp
- Dans les écrans de documents (`DocumentsTab.tsx` et `Travaux.tsx`), lors du clic sur le bouton WhatsApp :
  - Si le patient a un seul numéro, l'envoi s'effectue directement.
  - Si le patient a plusieurs numéros, un dialogue Radix s'affiche pour lister les numéros, leurs relations et un badge WhatsApp si compatible, permettant à l'utilisateur de choisir la ligne destinataire.

## Risks / Trade-offs

- **[Risk]** N+1 requêtes lors du listing des patients s'il faut charger les téléphones pour chaque patient.
  - *Mitigation* : Le listing des patients (`/patients`) n'a pas besoin de lister tous les téléphones secondaires. Il continue d'utiliser le champ plat `patients.telephone` (qui est maintenu synchronisé avec le numéro principal). Les téléphones secondaires ne sont chargés que via `GET /patients/{id}` (fiche détaillée).
- **[Risk]** Mauvaise interprétation de la saisie utilisateur si l'utilisateur saisit un indicatif dans le champ numéro en plus du sélecteur.
  - *Mitigation* : Nettoyer le numéro saisi par l'utilisateur en supprimant les indicatifs redondants ou les zéros initiaux superflus lors de la recomposition.
