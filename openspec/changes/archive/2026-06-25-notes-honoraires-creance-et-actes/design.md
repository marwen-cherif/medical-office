## Context

Le modèle financier actuel repose sur **deux sources de créance** coexistantes, unifiées dans la
vue Finances (`repo.list_creances`, UNION) :

- les **actes** (`prestations`) : créance partielle (`montant − montant_regle`), réglée par
  versements datés (`prestation_reglements`) ;
- les **paiements** (`paiements`) : créance « note » **binaire** (en_attente → encaisse), reliée
  optionnellement à un document via `paiements.document_id`.

Règle en vigueur (capability `plans-de-traitement`, restatée par `facturation-multi-lignes`) :
**« la génération d'une note ne crée jamais de paiement »** — le dû est porté exclusivement par
les actes. Concrètement aujourd'hui :

- note **mono-valeur** (modèle simple) → **aucune** dette enregistrée (`documents.montant` est
  purement affichage/email) ;
- note **multi-lignes** depuis actes existants cochés → pas de nouvelle dette ;
- note **multi-lignes** avec actes ajoutés à la volée → crée des **actes isolés** (`prestations`)
  qui portent la dette.

Les lignes d'une note multi-lignes sont sérialisées sous la clé réservée `__lignes__` de
`documents.variables` ; chaque ligne projette un acte via `generator.prestation_to_ligne`
(`{source, prestation_id, date, acte, dents, note, montant, regle}`) où `montant` **recopie**
le montant de l'acte. Les totaux sont **recalculés** au rendu (`compute_totaux`), jamais stockés.

Le besoin métier fait évoluer ce modèle sur trois axes (décisions utilisateur déjà tranchées) :

1. une note **non rattachée à un acte** doit engendrer une dette suivie (créance « note ») ;
2. le montant facturé sur une ligne de note peut **différer** du montant de l'acte ;
3. on doit pouvoir **générer une note depuis la page Actes/Plans** (sélection multiple ou acte
   unique via le menu « ⋮ »).

Contraintes : Windows-only (Word COM), **aucune migration destructive** (base de production
existante), engine `src/` non modifié, UI en cours de migration Flet → React (FastAPI + React).

## Goals / Non-Goals

**Goals :**

- Une note **autonome** (sans acte rattaché) crée une **créance « note »** (`paiement`
  en_attente) à la génération, rattachée au document, visible page Actes/Plans et Finances.
- Le **montant par ligne** d'une note adossée à un acte devient **éditable** (défaut = montant de
  l'acte), **affichage seul**, sans toucher l'acte ni la dette.
- Deux **points d'entrée** de génération de note depuis la page Actes/Plans : multi-sélection
  d'actes et action sur la ligne d'un acte.
- **Zéro migration de schéma** ; réutiliser `paiements` (+`document_id`) et `__lignes__`.

**Non-Goals :**

- Rattacher une **note mono-valeur** à un acte existant pour supprimer sa créance (pour facturer
  des actes existants, on passe par une **note multi-lignes** — point d'entrée dédié).
- **Resynchroniser** la créance « note » avec la note après création (cycle de vie indépendant,
  cf. décision utilisateur) : régénérer/supprimer la note ne touche pas la créance.
- Un **montant de note propre** pour un **nouvel acte** ajouté à la volée (le montant de la carte
  d'acte = montant de l'acte = montant de la ligne ; l'override ne concerne que les actes
  **existants** retenus).
- Toute modification du moteur `src/` ou du contrat de balises `<L_*>` des modèles `.docx`.

## Decisions

### D1 — Créance « note » via la table `paiements`, reliée par `document_id`

La dette d'une note autonome est un `paiement` en_attente créé par `repo.create_paiement`, avec
`document_id = doc.id`, `montant = documents.montant`, `statut = 'en_attente'`,
`notes = document.acte` (résumé) ou « Note d'honoraires ». **Aucune table ni colonne nouvelle** :
`paiements.document_id` existe déjà et `list_creances` / `creances_patient` / l'onglet « notes en
attente » consomment déjà les paiements en_attente. La créance apparaît donc immédiatement aux
trois endroits attendus sans nouveau code de lecture.

- *Alternative écartée* : un acte isolé (`prestation`) auto-créé pour porter la dette.
  Rejeté (choix utilisateur) — une note mono-valeur n'est pas un acte clinique ; la représenter
  comme un acte polluerait l'onglet Actes et le référentiel.

### D2 — Définition de « note autonome » et déclenchement

Une note est **autonome** ⇔ elle ne référence **aucun acte**. La détection combine deux signaux à
la génération :

- `generator.is_note_autonome(variables)` = `get_lignes(variables) is None` (note **multi-lignes**
  ⇒ référence toujours des actes ⇒ adossée) ;
- `has_actes` = au moins un acte transmis au flux `generate` (`body.selected_prestation_ids` ou
  `body.new_actes`). Ce signal couvre le cas où une note **mono-valeur** est **générée depuis un
  acte unique** (point d'entrée page Actes/Plans, cf. D5) : elle est alors **adossée** (l'acte
  porte le dû), donc **pas** de créance, bien qu'elle soit mono-valeur.

La créance est créée :

- **uniquement** quand `body.is_note` est vrai (les documents d'un autre type n'engendrent jamais
  de créance) ;
- **uniquement** si la note est autonome **et** `has_actes` est faux ;
- **uniquement** si `documents.montant > 0` (rien à facturer sinon) ;
- **à la génération** (route `generate`), pas à l'enregistrement du brouillon.

### D3 — Idempotence + indépendance de la créance (cycle de vie)

Avant création, on vérifie qu'**aucun** `paiement` n'est déjà rattaché à ce `document_id`
(nouveau helper lecture `repo.get_paiement_by_document`) : si présent, on **ne crée pas** de
doublon et on **ne met pas à jour** l'existant. Après création, la créance est **indépendante** :
supprimer ou régénérer la note ne la modifie ni ne la supprime (choix utilisateur). L'utilisateur
la gère via « Encaisser » / « Annuler » (page Actes/Plans ou Finances).

- *Conséquence assumée* : si le montant de la note change après une première génération, la
  créance garde l'**ancien** montant (elle est indépendante). Tracé dans Risks.

### D4 — Montant de ligne *override* dans `__lignes__` (affichage seul)

Le champ `montant` d'une ligne `__lignes__` porte désormais le **montant de note** (éditable),
dont la **valeur par défaut** reste le montant de l'acte au moment du regroupement. Le montant
réel de l'acte n'est **pas** stocké dans la ligne : la dette se lit en direct depuis
`prestations` (endpoint clinique), donc l'écart note/acte n'a **aucun** effet sur la dette.
`compute_totaux` / `_ligne_to_row_repl` restent inchangés (ils opèrent sur le `montant` de la
ligne) ; `regle` continue de refléter l'acte.

Côté API :

- `GenActeLine` (formulaire) gagne un champ **`montant_note`** (défaut = montant de l'acte, ou le
  montant édité restitué depuis `__lignes__` d'un brouillon) ;
- le corps `DraftIn` transporte le **montant par ligne retenue** (p. ex. une map
  `prestation_id → montant`, ou des lignes enrichies), consommé par `_build_lignes` pour fixer le
  `montant` de la ligne (au lieu de recopier l'acte).

- *Alternative écartée* : stocker à la fois `montant_acte` et `montant_note` dans la ligne.
  Inutile — le montant d'acte fait foi et se lit en direct ; le dupliquer créerait un snapshot
  trompeur.

### D5 — Points d'entrée depuis la page Actes/Plans (réutilisation du flux existant)

Aucune nouvelle route backend : les deux points d'entrée **pré-remplissent** le `GenerateDialog`
(mode `note`) avec des `selected_prestation_ids` initiaux ; la génération réutilise
`POST /patients/{id}/documents/generate`. Côté React :

- **Multi-sélection** : `PlansActesTab` gagne un mode sélection (cases à cocher sur les lignes
  d'actes isolés et de plans) + une barre d'action « Générer une note d'honoraires (N) » qui ouvre
  le dialogue avec la sélection.
- **Action par ligne** : un **menu « ⋮ »** par ligne d'acte (aujourd'hui : boutons inline Régler /
  Modifier / Supprimer) reçoit l'entrée « Générer une note d'honoraires » → ouvre le dialogue avec
  ce seul acte.

Le sélecteur de modèle du dialogue reste filtré sur la **catégorie « Notes d'honoraires »** (mode
`note`). Le **modèle privilégié à l'ouverture dépend du nombre d'actes** (l'utilisateur peut le
changer) :

- **≥ 2 actes** → premier modèle **multi-lignes** (rend les actes en lignes) ;
- **1 acte** → premier modèle **mono-valeur**, dont les champs sont **pré-remplis depuis l'acte**.
  `generation_form` accepte `source_prestation_id` et mappe les balises standard (ACTE ← libellé,
  MONTANT ← montant, DATE ← date, DENTS, NOTE) ;
- **0 acte** (« note sans acte ») → premier modèle **mono-valeur** vierge (note autonome).

`GenTemplateOut` expose `is_multiligne` (calculé via `classify_placeholders`, sans Word) pour ce
choix côté frontend. Le `RowActions` (menu ⋮) est rendu **non-modal** (`modal={false}`) : sinon le
verrou `pointer-events` du menu reste sur le `<body>` après ouverture d'un dialogue (UI bloquée).

- *Alternative écartée* : une route dédiée « générer note pour actes ». Superflue — le contrat
  `selected_prestation_ids` existe déjà et couvre exactement ce besoin.

### D6 — Spécifications : centraliser la règle de dette dans `plans-de-traitement`

La règle « quand une note crée-t-elle une dette » est **une** règle financière : on la centralise
dans `plans-de-traitement` › « Source unique du dû » (MODIFIED, conditionnelle) et on **retire**
la règle redondante « Aucun paiement créé à la génération » de `facturation-multi-lignes`
(REMOVED). `facturation-multi-lignes` ne garde que ce qui lui est propre : montant de ligne
éditable et points d'entrée (ADDED).

## Risks / Trade-offs

- **Double-comptage si mauvaise détection « autonome »** → Mitigation : gating strict
  (`is_note` ∧ mono-valeur ∧ `montant > 0`) ; les notes multi-lignes sont toujours adossées ;
  idempotence par `document_id` (D3).
- **Créance figée après changement de montant de note** (D3, indépendance) → Mitigation :
  comportement documenté et voulu ; l'utilisateur ajuste la créance à la main. Réversible plus
  tard (passer à un cycle « lié au document » si besoin).
- **Écart note/acte mal interprété** (un agent voit 600 sur la note, 950 sur l'acte) →
  Mitigation : la spec pose explicitement « l'acte fait foi, la note est affichage » ; l'UI peut
  signaler visuellement une ligne dont le montant diffère de l'acte.
- **`documents.montant` ambigu** (affichage **et** base de la créance note) → Mitigation : la
  créance n'est créée que pour les notes **autonomes**, où `documents.montant` = le dû ; pour les
  notes adossées il reste pur affichage. La règle conditionnelle lève l'ambiguïté.
- **Régression du flux multi-lignes existant** (montant désormais éditable) → Mitigation : défaut
  inchangé (= montant de l'acte) ; tests de non-régression sur un brouillon multi-lignes existant.

## Migration Plan

1. **Backend** : helper `repo.get_paiement_by_document` (lecture) ; création conditionnelle de la
   créance dans `generator.render_document` (ou la route `generate`) ; `_build_lignes` accepte un
   montant par ligne ; `generation_form` restitue `montant_note`.
2. **Frontend** : champ montant éditable par ligne dans `GenerateDialog` ; mode sélection +
   menu « ⋮ » dans `PlansActesTab` ; régénération des types (`schema.d.ts`).
3. **Aucune** étape de migration de base (pas de schéma modifié) ; `SCHEMA_VERSION` **inchangé**.
4. **Rollback** : revenir au binaire précédent est sûr (les `paiements` créés restent des notes en
   attente standard, déjà gérées par toutes les versions ; `__lignes__` reste lisible — un montant
   édité y est juste une valeur comme une autre).
5. **Recette** (manuelle, Word requis) : note mono-valeur → créance visible ; note multi-lignes
   adossée avec montant édité → acte et dette inchangés ; régénération → pas de doublon de créance ;
   points d'entrée page Actes/Plans → dialogue pré-rempli, aucune dette.

## Open Questions

- **Échéance de la créance « note »** : `date_echeance` à NULL par défaut (apparaît en dernier au
  tri des créances), ou = date d'émission de la note ? Proposé : NULL, ajustable par l'utilisateur.
- **Signalement visuel** d'une ligne dont le montant de note diffère du montant de l'acte
  (badge / pastille) : souhaitable mais non bloquant pour la V1.
