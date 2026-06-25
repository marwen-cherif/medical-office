## 1. Backend — créance « note » pour une note autonome

- [x] 1.1 Ajouter `repo.get_paiement_by_document(conn, document_id)` (lecture) renvoyant le `paiement` rattaché à un document, ou `None` (sert à l'idempotence).
- [x] 1.2 Dans `crm/generator.py`, ajouter un helper `is_note_autonome(variables)` : vrai si la note ne référence aucun acte (`get_lignes(variables) is None`, c.-à-d. note mono-valeur).
- [x] 1.3 Créer la créance « note » à la génération : après `render_document`, si `is_note` ∧ note autonome ∧ `documents.montant > 0` ∧ aucun paiement déjà rattaché (1.1), créer un `repo.create_paiement` (`document_id`, `montant = documents.montant`, `statut='en_attente'`, `notes = document.acte` ou « Note d'honoraires », `date_echeance = NULL`). Journaliser (`log_audit`, action ex. `creance_note_creee`).
- [x] 1.4 Implanter cet appel au bon endroit du flux `generate` (`crm/routers/documents.py`, tâche du job) pour que la génération par lot et la fiche patient en bénéficient ; ne **pas** créer au brouillon.
- [x] 1.5 Vérifier la non-régression : une note **adossée à des actes** (multi-lignes) ne crée **aucun** paiement ; un document d'un **autre type** non plus.

## 2. Backend — montant de ligne éditable (affichage seul)

- [x] 2.1 `crm/routers/documents.py` : `_build_lignes` accepte un **montant par ligne retenue** (override) et le pose comme `montant` de la ligne `__lignes__` au lieu de recopier le montant de l'acte ; défaut = montant de l'acte si non fourni.
- [x] 2.2 Étendre le contrat d'entrée (`DraftIn`) : transporter le montant de note par acte retenu (ex. map `prestation_id → montant`, ou lignes enrichies) ; rétro-compatibilité si absent (défaut acte).
- [x] 2.3 `generation_form` : enrichir `GenActeLine` d'un champ `montant_note` (défaut = montant de l'acte ; pour un brouillon, restituer le montant **édité** lu depuis `__lignes__`).
- [x] 2.4 Confirmer que `compute_totaux` / `_ligne_to_row_repl` opèrent bien sur le `montant` (override) sans modification, et que `regle`/`reste` continuent de refléter l'acte.
- [x] 2.5 S'assurer qu'aucune écriture ne touche `prestations` quand seul le montant de note change (l'acte fait foi, jamais modifié par la note).

## 3. Backend — points d'entrée depuis la page Actes/Plans

- [x] 3.1 Confirmer qu'aucune nouvelle route n'est nécessaire : la pré-sélection passe par `selected_prestation_ids` du flux `generate`/`draft` existant.
- [x] 3.2 (Si besoin) exposer/valider que `generation_form` accepte une pré-sélection initiale d'actes cochés transmise par le frontend.

## 4. API / types

- [x] 4.1 Régénérer le schéma OpenAPI (`ui/openapi.json`) puis les types TS (`ui/src/api/schema.d.ts`) après les changements de modèles Pydantic.
- [x] 4.2 Mettre à jour les ré-exports `ui/src/api/types.ts` (`GenActeLine.montant_note`, `DraftIn` montant par ligne). — Aucun changement requis : `GenActeLine`/`DraftIn`/`GenerateIn` réexportent les schémas entiers, les nouveaux champs sont inclus d'office.

## 5. Frontend — montant éditable par ligne (GenerateDialog)

- [x] 5.1 `ui/src/screens/patient-detail/GenerateDialog.tsx` : afficher un champ **montant** éditable par acte retenu (défaut = `montant_note`), pour les actes **existants** sélectionnés.
- [x] 5.2 Recalculer les totaux affichés (`totals`) à partir des montants de note édités.
- [x] 5.3 Inclure les montants de note édités dans `buildBody` (brouillon et génération).
- [x] 5.4 Restituer les montants édités à la réouverture d'un brouillon (depuis `montant_note`).
- [x] 5.5 (Optionnel) signaler visuellement une ligne dont le montant de note diffère du montant de l'acte.

## 6. Frontend — page Actes/Plans (sélection multiple + menu ⋮)

- [x] 6.1 `ui/src/screens/patient-detail/PlansActesTab.tsx` : ajouter un **mode sélection** (cases à cocher sur les lignes d'actes isolés et de plans).
- [x] 6.2 Ajouter une barre d'action « Générer une note d'honoraires (N) » qui ouvre `GenerateDialog` en mode `note` avec `selected_prestation_ids` = sélection.
- [x] 6.3 Ajouter un **menu d'actions « ⋮ »** par ligne d'acte (`PrestationRow`) contenant « Générer une note d'honoraires » → ouvre `GenerateDialog` avec ce seul acte pré-coché.
- [x] 6.4 Brancher l'ouverture du dialogue pré-rempli (état `gen` / props `selectedPrestationIds`) ; filtrer le sélecteur de modèle sur la catégorie « Notes d'honoraires » (multi-lignes).
- [x] 6.5 Vérifier que la page « notes en attente » affiche bien la nouvelle créance « note » après génération d'une note autonome (invalidation react-query `clinicalKeys`).

## 7. Tests & recette (Windows + Word requis)

- [x] 7.1 Note **mono-valeur** de 300 sans acte → génération → créance « note » de 300 visible sur Actes/Plans et Finances ; total à recouvrer +300.
- [x] 7.2 Note **multi-lignes** depuis un acte de 950 avec montant de note édité à 600 → la note affiche 600, l'acte reste à 950, la dette du patient inchangée.
- [x] 7.3 **Régénération** d'une note autonome → pas de seconde créance ; suppression de la note → la créance subsiste (indépendante).
- [x] 7.4 Points d'entrée page Actes/Plans (multi-sélection + menu ⋮) → dialogue pré-rempli, génération sans nouvelle dette.
- [x] 7.5 Non-régression : ouverture d'une base de production existante (documents mono-valeur et multi-lignes antérieurs) → chargement/rendu inchangés, `SCHEMA_VERSION` non bumpé.

## 8. Documentation

- [x] 8.1 Mettre à jour `CLAUDE.md` (section facturation multi-lignes / source unique du dû) pour refléter la règle conditionnelle (note autonome → créance ; note adossée → pas de paiement) et le montant de ligne éditable.
- [x] 8.2 À l'archivage : synchroniser les specs principales (`openspec/specs/plans-de-traitement`, `facturation-multi-lignes`) via le flux d'archive.
