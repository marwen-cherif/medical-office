## 1. Migration du journal d'audit (v11)

- [x] 1.1 Bump `SCHEMA_VERSION` 10 → 11 dans `crm/db.py`
- [x] 1.2 Ajouter une étape `_migrate()` idempotente, gardée par `_column_exists`, qui fait `ALTER TABLE audit_log ADD COLUMN patient_id INTEGER` (nullable, sans FK)
- [x] 1.3 Créer l'index `CREATE INDEX IF NOT EXISTS idx_audit_patient ON audit_log(patient_id, id DESC)` (dans `_migrate`, APRÈS l'ALTER — pas dans `_SCHEMA`)
- [x] 1.4 Mettre à jour le `_SCHEMA` (CREATE TABLE de référence) pour refléter la nouvelle colonne sur une base fraîche
- [x] 1.5 S'assurer que le snapshot pré-migration labellisé (`cabinet-pre-v11-…db`, exempt du prune `KEEP=10`) est pris **avant** la migration (assuré par `connect()` via le bump de version — testé)
- [x] 1.6 Vérifier l'anti-downgrade (`SchemaTooNewError`) et l'ouverture d'une base v10 existante (migration sans perte) — testé sur base v10 jetable

## 2. Couche données : journal structuré (`crm/repo.py`)

- [x] 2.1 Étendre `log_audit(conn, action, detail="", *, patient_id=None)` : sérialiser `detail` en JSON s'il s'agit d'un dict, accepter une chaîne (rétrocompat), rester best-effort
- [x] 2.2 Ajouter `list_audit_patient(conn, patient_id, limit=200)` retournant les événements du patient en ordre antichronologique
- [x] 2.3 Rendre la lecture tolérante : `parse_audit_detail` (`json.loads` avec repli sur l'affichage brut si le `detail` n'est pas un JSON valide — anciennes lignes)
- [x] 2.4 Faire calculer à `update_patient` le diff des champs (nom, prénom, email, téléphone, date_naissance, adresse, notes) **avant** l'UPDATE et exposer/journaliser `{champ: [avant, après]}` (champs inchangés exclus) — via `diff_patient`
- [x] 2.5 Conserver le comportement global de `list_audit` (Paramétrage) inchangé

## 3. Journalisation des événements aux points de mutation

- [x] 3.1 `fiche_creee` à la création de patient (avec `patient_id`)
- [x] 3.2 `fiche_modifiee` à la mise à jour de patient, `detail` = champs modifiés avant→après
- [x] 3.3 `plan_cree` / `plan_modifie` / `plan_supprime` (avec `patient_id`, titre du plan)
- [x] 3.4 `acte_ajoute` / `acte_modifie` / `acte_supprime` (avec libellé, dents si présentes)
- [x] 3.5 `acte_regle` au règlement d'un acte (montant, mode) + `reglement_cascade` / `paiement_encaisse` / `paiement_annule`
- [x] 3.6 `document_genere` avec type/modèle ; `note_honoraires_generee` pour les notes d'honoraires
- [x] 3.7 `document_envoye` à l'envoi email
- [x] 3.8 Reprendre les appels `log_audit` existants pour leur passer `patient_id` + `detail` JSON (homogénéiser les types d'action en `snake_case`) — brouillons, impression inclus
- [x] 3.9 Recenser et cocher chaque point de mutation (patient / plan / acte / règlement / document) pour garantir la couverture complète (dépenses fournisseurs = prestataire, hors périmètre patient)

## 4. Refonte de la disposition de la fiche (`crm/app.py`)

- [x] 4.1 Transformer `show_patient_detail` en `ft.Row([identite, contenu])` : colonne d'identité figée (largeur fixe) + zone de contenu extensible
- [x] 4.2 Construire la colonne d'identité compacte : retour, nom, email/téléphone cliquables (copie via `_id_field`), date de naissance, adresse, résumé Dû / Reste, bouton « Modifier » (+ raccourci conservé)
- [x] 4.3 Mettre en place `ft.Tabs` (API récente : `TabBar` + `TabBarView`) avec les onglets « Plans & actes », « Documents », « Règlements », « Historique » (onglet par défaut : Plans & actes), contenu en `Column(scroll=AUTO)`, onglet actif mémorisé
- [x] 4.4 Onglet « Plans & actes » : réutiliser `_plans_actes_section` / `_plan_tile` / `_prestation_row` et les actions Plan / Acte / Régler sans régression
- [x] 4.5 Onglet « Documents » : réutiliser `_grouped_docs_column` / `_doc_row`, la pagination et les actions (Note d'honoraires, Générer, Rafraîchir les statuts, ouvrir/imprimer/envoyer/rafraîchir)
- [x] 4.6 Onglet « Règlements » : réutiliser `_money_summary` / `_encaissement_row` et la pagination
- [x] 4.7 Gérer la largeur étroite (web) : seuil (`page.width < 860`) en-dessous duquel l'identité repasse au-dessus du contenu (dégradation gracieuse)

## 5. Onglet Historique (`crm/app.py`)

- [x] 5.1 Ajouter le mapping type d'action → catégorie / icône / libellé lisible (`_AUDIT_META`, en tête de fichier)
- [x] 5.2 Implémenter `_historique_tab(patient_id)` : lecture via `list_audit_patient`, regroupement par jour (« Aujourd'hui » / « Hier » / date), entrées icône + libellé + heure
- [x] 5.3 Afficher pour `fiche_modifiee` les lignes « champ : avant → après » sous l'entrée
- [x] 5.4 Ajouter la rangée de filtres (Tous / Fiche / Plans / Actes / Documents / Règlements) re-filtrant la liste
- [x] 5.5 Gérer l'état vide (« Aucun historique ») et la mention de troncature au-delà de la limite de lecture (200)

## 6. Vérification manuelle (Windows + Word requis)

> Portes de pré-livraison à exécuter dans l'app réelle (GUI/Word). Les équivalents
> automatisés ont été passés pour la couche données et le rendu de l'historique
> (migration v10→v11, journal par patient, tolérance des anciennes lignes, filtres,
> avant/après) ; le reste relève du visuel et de Word.

- [x] 6.1 Copier une `cabinet.db` de production (`backups/`), lancer le nouveau build : patients/documents/plans/actes/règlements chargent et s'affichent
- [x] 6.2 Vérifier la parité fonctionnelle : chaque action de la fiche actuelle est retrouvée dans un onglet ou la colonne d'identité (checklist)
- [x] 6.3 Déclencher chaque type d'événement et vérifier son apparition correcte dans l'onglet Historique (icône, libellé, regroupement, avant/après)
- [x] 6.4 Vérifier la tolérance des anciennes lignes (`patient_id` NULL, `detail` non-JSON) sans erreur d'affichage
- [x] 6.5 Vérifier l'affichage en mode desktop et en mode web (dont fenêtre étroite)
