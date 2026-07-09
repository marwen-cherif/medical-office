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
  est saisi à la main) SHALL, **par défaut**, créer à la génération une **créance « note »** (un
  `paiement` en_attente) rattachée au document (`paiements.document_id`). La note est alors
  elle-même la source du dû. Cette création SHALL être **un choix de l'utilisateur exposé au
  moment de la génération** (option « tracer la note en attente »), **activé par défaut** :
  - Quand l'option est **désactivée**, **aucune** créance ne SHALL être créée ; la note est
    générée comme un document purement informatif.
  - Quand l'option est **activée**, le **montant de la créance** SHALL être **paramétrable
    indépendamment** du montant affiché/imprimé sur le document — défaut = montant du document.
    Ce montant de créance ne SHALL **pas** modifier le rendu ni le `documents.montant` du
    document. La créance ne SHALL être créée que si ce montant est **strictement positif**.

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

#### Scenario: Note autonome tracée par défaut
- **WHEN** l'utilisateur génère une note mono-valeur de 300 sans rattacher d'acte et **sans
  toucher** à l'option de suivi (cochée par défaut, montant pré-rempli à 300)
- **THEN** une créance « note » (paiement en attente) de 300, rattachée au document, est créée et
  apparaît dans les notes en attente de la page Actes/Plans et dans l'écran Finances

#### Scenario: Note autonome générée sans suivi
- **WHEN** l'utilisateur **décoche** l'option « tracer la note en attente » puis génère une note
  mono-valeur autonome de 300
- **THEN** le document est généré normalement et **aucune** créance « note » n'est créée ; la
  note n'apparaît dans aucune liste de créances

#### Scenario: Montant de créance distinct du montant du document
- **WHEN** l'utilisateur génère une note autonome dont le document affiche 300, mais saisit **200**
  dans le champ « Montant à suivre »
- **THEN** la créance « note » créée porte **200**, tandis que le document imprimé/envoyé affiche
  toujours **300**

#### Scenario: Pas de créance pour un montant de suivi nul
- **WHEN** l'option de suivi est activée mais le « Montant à suivre » est **0** (ou vide, sans
  montant déductible du document)
- **THEN** aucune créance « note » n'est créée

#### Scenario: Pas de double créance si la note est régénérée
- **WHEN** une note autonome ayant déjà engendré une créance « note » est régénérée
- **THEN** aucune seconde créance n'est créée (la créance existante, rattachée au document, est
  conservée telle quelle), quelles que soient les valeurs de l'option de suivi et du montant

#### Scenario: Nouvel acte ajouté depuis une note reste un acte
- **WHEN** l'utilisateur ajoute un acte à la volée depuis une note puis génère
- **THEN** un acte (prestation) est créé et porte le dû ; aucun paiement n'est créé pour cet acte
