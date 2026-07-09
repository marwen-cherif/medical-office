## MODIFIED Requirements

### Requirement: Source unique du dû (pas de double-comptage)

Créer un acte facturable ne SHALL PAS créer de ligne de paiement : l'acte (prestation) est
lui-même la créance, **source du dû**.

La **génération d'une note d'honoraires** SHALL appliquer une règle **conditionnelle**, selon que
la note est **adossée à des actes** ou **autonome** :

- Une note **adossée à au moins un acte** (acte existant retenu, ou acte ajouté à la volée — donc
  créé comme prestation) ne SHALL **jamais** créer de paiement : son dû est déjà porté par les
  actes (pas de double-comptage). Le total de la note SHALL renseigner `documents.montant`
  **uniquement** comme valeur d'affichage/email, et ne SHALL PAS apparaître comme une créance
  distincte des actes.
- Une note **autonome** (aucun acte rattaché — typiquement une note mono-valeur dont le montant
  est saisi à la main) SHALL créer, **à la génération**, une **créance « note »** (un `paiement`
  en_attente) rattachée au document (`paiements.document_id`), du **montant de la note**. La note
  est alors elle-même la source du dû.

Les **nouveaux actes** ajoutés depuis une note SHALL être créés comme **actes** (`prestations`),
jamais comme paiements. La génération d'un **document d'un autre type** (non note d'honoraires)
ne SHALL créer aucun paiement.

#### Scenario: Acte facturable sans paiement dupliqué
- **WHEN** l'utilisateur enregistre un acte facturable de 950
- **THEN** aucune ligne de paiement n'est créée ; la créance est portée par l'acte lui-même

#### Scenario: Note adossée à des actes sans paiement
- **WHEN** l'utilisateur génère une note d'honoraires regroupant des actes (existants et/ou
  ajoutés à la volée)
- **THEN** aucun paiement n'est créé, le dû du patient reste celui porté par ses actes, et le
  total de la note ne sert que d'affichage

#### Scenario: Note autonome créant une créance
- **WHEN** l'utilisateur génère une note mono-valeur de 300 sans rattacher d'acte
- **THEN** une créance « note » (paiement en attente) de 300, rattachée au document, est créée et
  apparaît dans les notes en attente de la page Actes/Plans et dans l'écran Finances

#### Scenario: Pas de double créance si la note est régénérée
- **WHEN** une note autonome ayant déjà engendré une créance « note » est régénérée
- **THEN** aucune seconde créance n'est créée (la créance existante, rattachée au document, est
  conservée telle quelle)

#### Scenario: Nouvel acte ajouté depuis une note reste un acte
- **WHEN** l'utilisateur ajoute un acte à la volée depuis une note puis génère
- **THEN** un acte (prestation) est créé et porte le dû ; aucun paiement n'est créé pour cet acte
