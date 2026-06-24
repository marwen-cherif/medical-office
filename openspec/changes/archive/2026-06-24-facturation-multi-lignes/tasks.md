## 1. Moteur Word : répétition de ligne de tableau (`src/doc_filler.py`)

- [x] 1.1 Étendre `extract_placeholders` pour distinguer **balises de ligne** (`L_*`, →
      colonnes) et **balises document**, sans casser l'API existante (toujours la liste à
      plat pour les consommateurs actuels)
- [x] 1.2 Détecter la **ligne-modèle** : repérer le `w:tr` contenant ≥ 1 balise `L_*` ;
      erreur explicite si plusieurs lignes-modèles ou structure non supportée (cellules
      fusionnées, tableau imbriqué)
- [x] 1.3 Ajouter une fonction **additive** `expand_table_rows(doc, line_rows)` : `deepcopy`
      du `w:tr` modèle par ligne retenue, insertion en frères après le modèle, remplissage de
      chaque copie via le **réutilisé** `_replace_in_para_elem` (par paragraphe de cellule,
      que `_fill_docx` ne traverse pas aujourd'hui), puis retrait du modèle (retrait simple si
      0 ligne)
- [x] 1.4 Brancher l'expansion dans `_fill_docx`/`fill_and_export_pdf` (paramètre optionnel
      `line_rows`) ; comportement **inchangé** quand aucune ligne-modèle n'est présente
- [x] 1.5 Vérifier le **rendu réel** (pas seulement la chaîne) : mise en forme préservée
      (gras, bordures, alignement) sur un `.docx` de test — **validé manuellement (Windows + Word)**

## 2. Pont CRM : contexte standard + génération multi-lignes (`crm/generator.py`)

- [x] 2.1 Définir le **contrat de balises** (constantes) : balises document totaux
      (`TOTAL_DU`, `TOTAL_REGLE`, `RESTE_A_PAYER`, `NB_ACTES`, alias `TOTAL`) et balises de
      ligne (`L_DATE`, `L_ACTE`, `L_DENTS`, `L_NOTE`, `L_MONTANT`, `L_REGLE`, `L_RESTE`)
- [x] 2.2 Projeter une `repo.Prestation` (et une ligne libre) en **ligne de contexte**
      `{ source, prestation_id?, date, acte, dents, note, montant, regle }` (cf. design D4)
- [x] 2.3 Calculer les **totaux** en Python (D5) : `TOTAL_DU`, `TOTAL_REGLE`,
      `RESTE_A_PAYER`, `NB_ACTES` ; formater montants via `format_montant`, `NB_ACTES` en
      entier ; montant de ligne libre manquant → 0
- [x] 2.4 Construire le `line_rows` formaté (dates `jj/mm/aaaa`, montants français) et le
      passer à `expand_table_rows` dans `render_document` ; conserver le chemin mono-valeur
      inchangé quand pas de `__lignes__`
- [x] 2.5 Sérialiser/désérialiser les lignes **brutes** sous la clé réservée `__lignes__` de
      `documents.variables` ; adapter `save_draft`/`update_draft` (totaux recalculés, aucun
      appel Word)
- [x] 2.6 Reporter le **total** sur `document.montant` (affichage/email **uniquement**, pas de
      créance — D6), fixer `document.acte_date` = 1re date des lignes, `document.acte` =
      résumé court optionnel (D8)
- [x] 2.7 Vérifier qu'**aucun paiement** n'est créé sur le chemin de génération de note (D6)
- [x] 2.8 Vérifier l'envoi Mailjet : variables d'email (total, 1re date, type) cohérentes pour
      une note multi-lignes

## 3. UI : dialogue « Note d'honoraires » multi-lignes (`crm/app.py`)

- [x] 3.1 Détecter le type « note multi-lignes » du modèle choisi (présence de balises `L_*`)
      et basculer vers l'éditeur multi-lignes ; sinon, conserver le formulaire mono-valeur
      actuel (`_resolve_fields`)
- [x] 3.2 Charger et présenter les **actes du patient** regroupés (Actes isolés via
      `list_prestations(plan_id=None)` ; par plan via `list_plans` + `list_prestations(plan_id)`),
      chaque acte avec **case pré-cochée** (date, libellé, montant, reste)
- [x] 3.3 Implémenter l'**ajout d'actes isolés** depuis la note : « + Ajouter un acte »
      empile la **carte d'acte réutilisée** (`_acte_card` : référentiel + odontogramme),
      créés via `repo.create_prestation` (plan_id=NULL) à l'enregistrement, suppression par
      carte *(remplace les « lignes libres » non tracées : UX plus simple, dû suivi sur l'acte)*
- [x] 3.4 Afficher le **total recalculé en direct** (dû / réglé / reste) à chaque
      (dé)sélection d'acte ou saisie de ligne libre, sans génération
- [x] 3.5 Intégrer dans le cycle brouillon → génération → envoi ; la reprise d'un brouillon
      multi-lignes restitue lignes, ordre et (dé)sélections depuis `__lignes__`
- [x] 3.6 (Optionnel) Réordonnancement des lignes par glisser-déposer
      (`ft.ReorderableListView`) si le coût UI le permet ; sinon ordre déterministe (isolés
      puis plans par date, lignes libres en fin)
      *(choix : ordre déterministe — actes isolés, puis par plan, lignes libres en fin ;
      glisser-déposer différé)*

## 4. Documentation

- [x] 4.1 Documenter le **contrat de variables standard** (balises document + balises de
      ligne `L_*`) et la convention d'écriture d'un modèle « note multi-lignes » (une seule
      ligne-modèle de tableau) — CLAUDE.md / aide modèle
- [x] 4.2 Noter explicitement l'**abandon** de l'évaluateur de formules et de la migration
      `template_fields.scope/expression` par rapport à la conception initiale

## 5. Validation de bout en bout (Windows + Word requis)

- [x] 5.1 Créer un modèle `.docx` « note multi-lignes » de test (ligne-modèle
      `<L_DATE> | <L_ACTE> | <L_DENTS> | <L_MONTANT>`, plus `<TOTAL_DU>`, `<TOTAL_REGLE>`,
      `<RESTE_A_PAYER>`, `<NB_ACTES>`)
      *(livré : `tools/make_sample_note_template.py` → `templates/note_multi_lignes_demo.docx`,
      structure validée hors Word)*
- [x] 5.2 Générer une note regroupant 4 actes (01/05, 02/05, 05/05, 01/06) : vérifier lignes,
      mise en forme, `TOTAL_DU = 390,000`, `NB_ACTES = 4` — **validé manuellement (Windows + Word)**
- [x] 5.3 Vérifier la sélection : décocher un acte le retire des lignes et des totaux ;
      **ajouter un acte** l'inclut (et le crée comme acte isolé) — **validé manuellement**
- [x] 5.4 Vérifier qu'**aucun paiement** n'est créé ; un acte existant coché n'augmente pas la
      dette du fait de la note (pas de double-comptage), un acte **nouvellement créé** l'augmente
      via l'acte (suivi attendu) — **validé manuellement**
- [x] 5.5 Vérifier la **non-régression** mono-valeur : un modèle simple existant se
      génère/s'envoie/s'imprime comme avant ; un document existant se charge intact —
      **validé manuellement (Windows + Word)**
- [x] 5.6 Vérifier les cas limites : 0 ligne retenue (tableau vide, pas de balise non remplie),
      carte d'acte incomplète ignorée / montant invalide bloquant, rechargement d'un brouillon
      multi-lignes — **validé manuellement**
