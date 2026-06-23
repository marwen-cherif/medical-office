# plans-de-traitement

## Purpose

Suivre les soins d'un patient **dans le temps** au moyen d'**actes réalisés** — rattachés
ou non à un **plan de traitement** (simple regroupement nommé, sans statut ni cycle de
vie). Chaque acte porte **à la fois le dû et le paiement** : libellé et prix sont
pré-remplis (snapshot modifiable) depuis le référentiel d'actes (`referentiel-actes`), et le
suivi se fait par **règlements partiels datés**, **reste à payer** et **barres de
progression** — calqué sur le mécanisme des dépenses fournisseurs. L'introduction des plans
et des actes est **purement additive** : elle ne modifie ni la table `paiements` ni les flux
existants.

## Requirements

### Requirement: Acte réalisé rattaché ou non à un plan
Le système SHALL permettre d'enregistrer un **acte réalisé** sur un patient, portant un
libellé, un montant et une date. Un acte SHALL pouvoir être **rattaché à un plan de
traitement** ou exister **sans plan** (acte isolé). Le rattachement à un plan SHALL pouvoir
être ajouté ou retiré sans perte d'information.

#### Scenario: Acte isolé sans plan
- **WHEN** l'utilisateur ajoute un détartrage à un patient sans choisir de plan
- **THEN** l'acte est enregistré comme acte isolé (sans plan) et apparaît sur la fiche du
  patient

#### Scenario: Acte rattaché à un plan
- **WHEN** l'utilisateur ajoute un acte en le rattachant au plan « Implant 26 »
- **THEN** l'acte apparaît dans le plan « Implant 26 » du patient

### Requirement: Pré-remplissage depuis le référentiel d'actes
Lors de l'ajout d'un acte, le système SHALL permettre de **choisir un acte du référentiel**
(`referentiel-actes`) et SHALL pré-remplir le **libellé** et le **prix** de la prestation à
partir de cet acte. Les valeurs pré-remplies SHALL rester **modifiables**. Le prix retenu
SHALL être **figé sur la prestation** (snapshot) : une modification ultérieure du prix de
l'acte dans le référentiel ne SHALL PAS modifier les actes déjà enregistrés.

#### Scenario: Pré-remplissage du libellé et du prix
- **WHEN** l'utilisateur choisit l'acte « Couronne céramique » (950) du référentiel
- **THEN** le libellé « Couronne céramique » et le prix 950 sont pré-remplis, modifiables

#### Scenario: Prix figé après changement du référentiel
- **WHEN** le prix de « Couronne céramique » passe de 950 à 1000 dans le référentiel après
  qu'un acte a été enregistré à 950
- **THEN** l'acte déjà enregistré conserve son montant 950

### Requirement: Plan de traitement comme regroupement éditable sans statut
Le système SHALL permettre de créer un **plan de traitement** rattaché à un patient,
portant un **titre** et regroupant des actes. Le plan SHALL être **éditable à tout moment**
(ajout, retrait, modification d'actes). Le plan ne SHALL PAS porter de statut ni de cycle de
vie (ni brouillon, ni clôture, ni abandon).

#### Scenario: Édition d'un plan à tout moment
- **WHEN** l'utilisateur ajoute un nouvel acte à un plan existant
- **THEN** l'acte est ajouté au plan sans contrainte d'état du plan

#### Scenario: Absence de clôture
- **WHEN** l'utilisateur consulte un plan
- **THEN** aucune action de clôture/changement de statut de plan n'est proposée, et l'ajout
  de paiements reste toujours possible

### Requirement: Composition d'un plan par cartes d'actes
Le système SHALL permettre de composer un plan en empilant des **cartes d'acte** — chaque
carte exposant les mêmes champs que l'ajout d'un acte (libellé, prix, date, dents, note) et
un **bouton de suppression**. Le système SHALL afficher le **total dû du plan recalculé en
direct** au fil des ajouts/retraits. La même carte d'acte SHALL servir pour l'ajout d'un
acte isolé.

#### Scenario: Ajout et retrait de cartes d'acte
- **WHEN** l'utilisateur ajoute deux cartes d'acte puis en supprime une
- **THEN** le plan ne retient que la carte restante et le total dû est recalculé en
  conséquence

### Requirement: Acte non facturable à montant nul (sans notion de type)
Le système ne SHALL PAS exposer de notion de « type » d'acte. Un acte de **contrôle** (ou
tout geste non facturé) SHALL se saisir comme un **acte à montant nul**. Un acte à montant
nul SHALL être **non facturable** : il ne SHALL PAS apparaître parmi les actes à régler, ne
SHALL PAS porter de barre de progression de paiement, et SHALL afficher un indicateur
**dérivé** « non facturable ». Un tel acte SHALL porter une **date** (éventuellement future)
pour planifier la visite.

#### Scenario: Contrôle saisi comme acte à 0
- **WHEN** l'utilisateur ajoute « Consultation de contrôle » à 0 avec une date future
- **THEN** l'acte apparaît avec sa date, sans barre de paiement, marqué « non facturable »,
  et hors de la liste des actes à régler

### Requirement: Dents concernées en notation FDI (optionnel)
Le système SHALL permettre de renseigner, **en option**, les **dents concernées** par un
acte en **notation FDI**, saisies sous forme de chips (un numéro par chip) et persistées en
chaîne séparée par des virgules. Le champ SHALL rester **facultatif** et la validation FDI
SHALL être **non bloquante** (suggestion). Les dents renseignées SHALL être affichées avec
l'acte sur la fiche patient.

#### Scenario: Saisie de plusieurs dents
- **WHEN** l'utilisateur saisit les dents 26 puis 27 sur un acte
- **THEN** l'acte mémorise « 26, 27 » et les affiche avec l'acte

#### Scenario: Champ dents laissé vide
- **WHEN** l'utilisateur enregistre un acte sans renseigner de dent
- **THEN** l'acte est enregistré sans information de dent et reste valide

### Requirement: Note libre par acte (optionnel)
Le système SHALL permettre d'attacher, **en option**, une **note libre** (texte
multi-lignes) à un acte. La note SHALL être affichée avec l'acte et SHALL être sans effet sur
la facturation.

#### Scenario: Note sur un acte
- **WHEN** l'utilisateur saisit la note « céramique pressée, teinte A2 » sur un acte
- **THEN** la note est mémorisée et affichée avec l'acte

### Requirement: Règlement partiel daté d'un acte
Le système SHALL permettre d'enregistrer un ou plusieurs **règlements datés** sur un acte
facturable, chaque règlement portant un montant et un mode (espèces / chèque / virement).
Le **cumul réglé** SHALL être maintenu et le **statut de paiement** de l'acte SHALL être
recalculé : `en_attente` (rien réglé), `regle_partiellement` (réglé en partie), `regle`
(soldé). Un règlement ne SHALL PAS pouvoir dépasser le reste à payer.

#### Scenario: Versement partiel
- **WHEN** l'utilisateur enregistre un versement de 300 sur un acte de 950 non réglé
- **THEN** l'acte affiche 300 réglé, 650 de reste, et le statut « réglé partiellement »

#### Scenario: Solde d'un acte
- **WHEN** l'utilisateur enregistre un versement égal au reste à payer
- **THEN** l'acte passe au statut « réglé » et son reste est nul

#### Scenario: Versement supérieur au reste refusé
- **WHEN** l'utilisateur saisit un versement supérieur au reste à payer
- **THEN** le versement est refusé avec un message indiquant le reste à payer

### Requirement: Reste et progression visibles par acte et par plan
Le système SHALL afficher, pour chaque acte facturable, son **reste à payer** et une **barre
de progression** (part réglée du montant). Pour un plan, le système SHALL afficher les
**totaux dérivés** — dû (somme des montants), encaissé (somme des cumuls réglés), reste — et
une **barre de progression** d'ensemble.

#### Scenario: Barre de progression d'un acte
- **WHEN** un acte de 950 a 300 réglés
- **THEN** sa barre de progression indique environ un tiers et affiche « 300 / 950 · reste
  650 »

#### Scenario: Totaux d'un plan
- **WHEN** un plan regroupe des actes pour un dû total de 2 870 dont 1 100 encaissés
- **THEN** le plan affiche dû 2 870, encaissé 1 100, reste 1 770, avec sa barre de
  progression

### Requirement: Règlement global réparti automatiquement en cascade
À la demande de règlement, le système SHALL présenter **un seul dialogue** où l'utilisateur
saisit **un montant reçu unique** (pré-rempli au total à recouvrer des actes), un **mode** et
une **date**. Le système SHALL **répartir automatiquement** ce montant sur les **actes** non
soldés du patient **du plus ancien au plus récent**, en **paiement partiel** (le dernier acte
atteint restant partiel). Les **notes d'honoraires** (binaires) SHALL être **exclues de la
cascade** et SHALL se régler séparément en entier via « Encaisser ». Le système SHALL afficher
un **aperçu** de la répartition et SHALL **signaler** tout **reliquat non affectable** (vrai
trop-perçu) sans le consommer silencieusement. Le système SHALL également permettre un
**versement ciblé sur un acte précis**.

#### Scenario: Répartition en cascade d'un montant
- **WHEN** un patient a un acte A au reste 300 (plus ancien) et un acte B au reste 400, et que
  l'utilisateur saisit un montant reçu de 500
- **THEN** l'acte A est soldé (+300), l'acte B reçoit +200 (reste 200), et un aperçu le montre
  avant validation

#### Scenario: Reliquat non affectable signalé
- **WHEN** l'utilisateur saisit un montant supérieur au total des actes non soldés du patient
- **THEN** la part excédentaire est signalée comme « non affectée » et n'est pas enregistrée

#### Scenario: Notes réglées séparément
- **WHEN** un patient a une note d'honoraires en attente
- **THEN** la note n'apparaît pas dans la cascade « Régler » et se règle en entier via
  « Encaisser »

#### Scenario: Versement ciblé sur un acte
- **WHEN** l'utilisateur choisit « Régler cet acte » sur une ligne précise
- **THEN** un dialogue de versement (partiel ou solde) ne porte que sur cet acte

### Requirement: Historique des règlements unifié sur la fiche patient
La fiche patient SHALL présenter les **créances** (notes en attente, actes isolés, plans) au
**même endroit**, et un **historique des règlements unifié** regroupant les **versements
d'actes** et les **notes encaissées**, précédé d'un récap **Dû / Encaissé / Reste** consolidé.
Chaque versement d'acte SHALL apparaître dans cet historique (synchronisé avec les lignes
d'actes).

#### Scenario: Versement d'acte visible dans l'historique
- **WHEN** l'utilisateur règle un acte (en cascade ou ciblé)
- **THEN** le versement apparaît dans l'historique des règlements de la fiche et le récap
  Dû / Encaissé / Reste est mis à jour

### Requirement: Vue unifiée des créances et des paiements
L'écran Finances SHALL présenter, **au même endroit**, les **paiements en attente** (issus de
notes) et les **actes non soldés** (`reste > 0`) comme des créances à recouvrer. Côté
encaissé, il SHALL agréger les **paiements encaissés** et les **règlements d'actes**. Chaque
ligne SHALL conserver sa **nature** (note / acte) et son **action** propre (encaisser un
paiement / régler un acte). Les **totaux** à recouvrer et encaissés SHALL inclure les **deux
sources**.

#### Scenario: Créances d'actes et paiements regroupés
- **WHEN** un patient a un paiement en attente issu d'une note et un acte au reste positif
- **THEN** les deux apparaissent comme créances dans l'écran Finances, chacun avec son action
  propre

#### Scenario: Total à recouvrer incluant les actes
- **WHEN** l'écran Finances affiche le total à recouvrer
- **THEN** ce total additionne les paiements en attente et le reste des actes non soldés

### Requirement: Source unique du dû (pas de double-comptage)
Créer un acte facturable ne SHALL PAS créer de ligne de paiement : l'acte (prestation) est
lui-même la créance. La **génération d'un document** (note d'honoraires comprise) ne SHALL
**jamais** créer de paiement : le suivi du dû passe exclusivement par les actes, supprimant tout
chemin parallèle de création de dette via les documents.

#### Scenario: Acte facturable sans paiement dupliqué
- **WHEN** l'utilisateur enregistre un acte facturable de 950
- **THEN** aucune ligne de paiement n'est créée ; la créance est portée par l'acte lui-même

#### Scenario: Génération de document sans paiement
- **WHEN** l'utilisateur génère un document ou une note d'honoraires
- **THEN** aucun paiement n'est créé (aucune option de création de paiement n'est proposée)

### Requirement: Note d'honoraires — bouton dédié filtré par catégorie de modèles
Le système SHALL exposer, sur la fiche patient, un **bouton « Note d'honoraires » dédié** qui
ouvre un dialogue ne proposant que les **modèles de la catégorie configurée** comme « notes
d'honoraires ». La génération **générique** de document SHALL **exclure** les modèles de cette
catégorie. La catégorie cible SHALL être **configurable** (Paramétrage › Modèles), avec un **défaut
conventionnel « Notes d'honoraires »** appliqué quand le réglage n'est pas défini. La
comparaison de catégorie SHALL être **tolérante** aux espaces de bord et à la casse.

#### Scenario: Le dialogue de note ne propose que la bonne catégorie
- **WHEN** la catégorie des notes d'honoraires est configurée et l'utilisateur ouvre
  « Note d'honoraires »
- **THEN** seuls les modèles de cette catégorie sont proposés

#### Scenario: La génération générique exclut les notes
- **WHEN** l'utilisateur ouvre « Générer un document »
- **THEN** les modèles de la catégorie des notes d'honoraires n'y figurent pas

#### Scenario: Défaut sans configuration
- **WHEN** aucun réglage n'est défini mais un modèle est rangé dans une catégorie « Notes
  d'honoraires »
- **THEN** le bouton « Note d'honoraires » propose ce modèle (catégorie par défaut)

### Requirement: Préservation des paiements existants
L'introduction des plans et des actes ne SHALL PAS modifier la table `paiements` ni le visuel
« paiements en attente » existant. Les paiements déjà enregistrés SHALL continuer de
s'afficher et de fonctionner comme avant.

#### Scenario: Visuel des paiements inchangé
- **WHEN** la nouvelle version est installée sur une base contenant des paiements
- **THEN** l'écran des paiements en attente affiche les mêmes paiements qu'auparavant

### Requirement: Suppression non destructive de l'argent
Le système ne SHALL PAS permettre de supprimer un acte qui porte des règlements sans action
explicite préalable. La suppression d'un **plan** SHALL **détacher** ses actes (qui
deviennent des actes isolés) plutôt que de les supprimer, afin qu'aucun règlement ne soit
perdu.

#### Scenario: Suppression d'un plan préservant les actes
- **WHEN** l'utilisateur supprime un plan contenant des actes réglés
- **THEN** les actes deviennent des actes isolés du patient, leurs règlements sont conservés,
  et le plan est retiré

#### Scenario: Suppression d'un acte réglé bloquée
- **WHEN** l'utilisateur tente de supprimer un acte portant des règlements
- **THEN** la suppression est refusée tant que l'acte n'a pas été explicitement soldé/annulé

### Requirement: Préservation des données et migration additive
L'introduction des plans et des actes SHALL être **purement additive** : trois nouvelles
tables via `CREATE TABLE IF NOT EXISTS`, un bump de `SCHEMA_VERSION`, et un snapshot
pré-migration. Aucune donnée existante (patients, documents, paiements, fichiers générés) ne
SHALL être modifiée ou supprimée par la mise à niveau.

#### Scenario: Mise à niveau d'une base de production
- **WHEN** une base de production existante est ouverte par la nouvelle version
- **THEN** les tables de plans, d'actes et de règlements sont créées vides, les données
  existantes restent intactes, et un snapshot pré-migration est conservé
