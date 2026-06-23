## Context

Côté patient, l'argent vit dans `paiements` : un montant binaire (`en_attente` /
`encaisse`), rattaché au plus à **un** document, sans paiement partiel ni notion d'acte.
Côté fournisseur, le sous-système `depenses` / `depense_reglements` fait déjà exactement ce
qu'on veut côté patient : un **dû** (`montant`), un **cumul réglé** (`montant_regle`), un
**reste** dérivé, un **statut** à trois états et un **historique de règlements datés**, le
tout présenté avec un dialogue de versement (`_regler_depense`, `app.py`) réutilisable
quasi tel quel.

Le besoin : modéliser les **actes réalisés** d'un patient (rattachés ou non à un plan),
pré-remplis depuis le **référentiel d'actes** (`referentiel-actes`), payables **partiellement
et dans le temps**, avec **reste** et **barre de progression** — sans toucher `paiements`
(le visuel « paiements en attente » doit rester) ni la donnée de production.

Contraintes (CLAUDE.md) : schéma **expand-only**, non destructif, bump `SCHEMA_VERSION` +
migration idempotente gardée + snapshot pré-migration ; toute évolution suppose une base de
production existante.

## Goals / Non-Goals

**Goals :**

- Une unité **acte réalisé** (`prestations`) portant dû + paiement, rattachable ou non à un
  plan (`plan_id` nullable).
- **Plans de traitement** = regroupement nommé, **éditable à tout moment**, **sans statut**.
- **Paiement partiel daté** par acte (calque `depenses` / `depense_reglements`), **reste** et
  **barre de progression** par acte et par plan.
- **Pré-remplissage** libellé+prix depuis le référentiel d'actes (snapshot).
- Champs optionnels **dents concernées** (FDI) et **note** par acte.
- **Vue Finances unifiée** : créances d'actes (`reste > 0`) et paiements en attente affichés
  **au même endroit**, avec des totaux qui incluent les deux sources.
- `paiements` **inchangée dans son mécanisme** ; migration **purement additive**.

**Non-Goals :**

- **Pas de cycle de vie de plan** (ni brouillon, ni clôture, ni abandon) — décision produit
  explicite (cf. D4).
- **Pas de notion de « type » d'acte** : un contrôle est un acte à montant nul (cf. D5).
- **Règlement par montant global réparti en cascade** (du plus ancien au plus récent), pas de
  sélection multiple manuelle (cf. D9 révisé). Un versement ciblé sur un acte reste possible.
- **Pas d'odontogramme interactif** : la saisie des dents est textuelle (chips FDI), le
  schéma visuel cliquable est reporté (cf. D10).
- **Pas de génération de note d'honoraires** depuis un plan dans ce change (laissé à
  `facturation-multi-lignes`).
- Pas de changement du **mécanisme** de création / encaissement des paiements existants : ils
  sont seulement **affichés avec** les créances d'actes (vue unifiée, D7).
- Pas de modification de `paiements`, `documents`, ni du moteur `src/`.

## Decisions

### D1 — L'unité de base est l'acte réalisé ; le plan n'est qu'un regroupement
Une seule table `prestations` avec `plan_id` **nullable**. `plan_id = NULL` ⇒ acte isolé
(détartrage…) ; `plan_id` renseigné ⇒ acte appartenant à un plan. « Plan éditable au fil de
l'eau » = ajouter / retirer / modifier des lignes `prestations`. Aucune structure d'étape
spéciale.

### D2 — Facturation calquée sur les dépenses
`prestations` reprend `depenses` : `montant` (dû), `montant_regle` (cumul réglé), `statut`
(`en_attente` / `regle_partiellement` / `regle`), et une propriété dérivée `reste = montant
- montant_regle`. `prestation_reglements` calque `depense_reglements` (versement, mode,
`date_reglement`). `repo.add_prestation_reglement` calque `add_depense_reglement` (ajoute le
versement, incrémente le cumul, recalcule le statut). Le versement reprend l'ergonomie de
`_regler_depense` (Total dû / Déjà réglé / Reste + montant versé + mode + date).

### D3 — Snapshot du libellé et du prix depuis le référentiel
Ajouter un acte ⇒ choix dans `referentiel-actes` (`list_actes`), puis **copie** du libellé
et du prix dans la prestation (`libelle`, `montant`), modifiables. `acte_id` est conservé
pour information. Modifier le prix d'un acte du catalogue ensuite **ne modifie pas** les
prestations existantes (même esprit que `documents.categorie` / `documents.montant`).

### D4 — Aucun statut / cycle de vie sur le plan
Le plan n'a **pas** de statut (pas de brouillon, clôture, abandon). Il porte un **titre**,
des **notes** et regroupe des actes. Le suivi se lit via le **statut de paiement de chaque
acte** et les **barres de progression**. *Rétractation explicite* de l'idée initiale de
« clôture qui gèle les paiements » : jugée inutile par le produit.

### D5 — Pas de « type » d'acte : un contrôle est un acte à montant nul
Décision : **aucune colonne `type`**. Tout ce qu'un type `controle` aurait apporté se déduit
de `montant = 0` :

- **non facturable** ⇒ `reste = 0` automatiquement ;
- **exclu des actes « à régler »** ⇒ le filtre `reste > 0` l'écarte déjà ;
- **pas de barre de progression de paiement** ⇒ conditionnée à `montant > 0` ;
- **visite future planifiable** ⇒ portée par la **date**, pas par un type.

Un contrôle se saisit donc comme un acte à montant nul, idéalement via une entrée
« Consultation de contrôle » du **référentiel** à 0 (le référentiel accepte déjà un prix ≥
0). Un acte à `montant = 0` est rendu avec un badge **dérivé** « non facturable » — qu'il
s'agisse d'un contrôle ou d'un geste gratuit ; le **libellé** porte le sens.

- *Alternative écartée* : colonne `type` (acte/controle) — redondante avec `montant = 0`,
  ajoute un concept sans valeur.

### D6 — Une seule date par prestation
`prestations.date_acte` : date de réalisation, ou date **prévue** pour une visite à venir.
Champ unique et éditable — pas de double statut clinique prévu/réalisé en v1 (simplicité ;
une date future vaut « planifié »).

### D7 — Vue Finances unifiée : créances d'actes + paiements au même endroit
Le **mécanisme** des paiements ne change pas (flux d'encaissement existant préservé). Mais
l'écran *Finances › Paiements* devient une **vue unifiée des créances** : il agrège, au même
endroit, les **paiements en attente** (issus de notes) et les **actes au reste positif**
(`prestations.reste > 0`). Côté encaissé, les **règlements d'actes**
(`prestation_reglements`) sont agrégés avec les paiements encaissés (trésorerie complète).
Chaque ligne conserve sa **nature** (note vs acte) et son **action** propre (encaisser un
paiement / régler un acte). Les agrégats (KPI du tableau de bord, totaux à recouvrer /
encaissé) **incluent les deux sources**. Choix produit : *(b)* — tout voir au même endroit
dès la v1.

### D8 — Suppression non destructive de l'argent
Supprimer une **prestation qui a des règlements** est **interdit** (préserve la trace
financière) ; il faut d'abord la solder/annuler explicitement. Supprimer un **plan**
**détache** ses prestations en actes isolés (`plan_id = NULL`, via `ON DELETE SET NULL`) au
lieu de les détruire ; le plan vide est alors retiré. Aucun versement n'est jamais perdu par
une suppression de plan.

### D9 — Règlement GLOBAL réparti en cascade (RÉVISÉ)
> **Révision** (retour produit en cours d'implémentation) : l'approche initiale « acte par
> acte, aucune répartition d'un montant sur plusieurs actes » est **abandonnée**. C'est au
> contraire la **répartition automatique d'un montant unique** qui est retenue — le praticien
> encaisse une somme et le système remplit les créances tout seul.

L'action « Régler » ouvre **un seul dialogue** où l'on saisit **UN montant reçu** (pré-rempli
au total à recouvrer des actes), un **mode** et une **date**. Ce montant est **réparti
automatiquement** sur les **actes** non soldés du patient, **du plus ancien au plus récent**,
en **paiement partiel** (via `prestation_reglements` ; le dernier acte atteint reste
partiellement réglé).

**Les notes d'honoraires sont EXCLUES de la cascade** (révision suite à un essai utilisateur) :
une note (`paiements`) est **binaire** — soldée en entier ou pas, jamais partiellement — donc
l'inclure bloquait tout reliquat trop petit pour la couvrir (« X non affecté » alors que des
lignes restent dues). Les notes en attente se règlent **séparément**, en entier, via leur
bouton « Encaisser » (liste « Notes en attente » de la fiche, et écran Finances). La cascade
ne porte donc que sur des créances **réellement fractionnables**.

Un **aperçu** de la répartition se met à jour en direct pendant la saisie. Le **reliquat non
affectable** n'apparaît plus qu'en cas de **vrai trop-perçu** (montant supérieur au total des
actes), et il est **signalé**, jamais consommé silencieusement. Un **versement sur un acte
précis** reste possible (action « Régler cet acte » par ligne et depuis l'écran Finances).

- *Anciennement écarté, désormais retenu* : montant unique → somme répartie en cascade.
- *Écarté* : répartition au prorata du reste (moins intuitive que la cascade par date).
- *Écarté* : inclure les notes binaires dans la cascade (bloque les reliquats ; les notes se
  règlent en entier à part). Rendre les notes fractionnables serait une évolution lourde de
  `paiements` (hors périmètre).

### D10 — Saisie des dents : chips FDI (texte virgulé), optionnelle
Champ **optionnel** `dents` : numéros de dents en **notation FDI / ISO 3950** (standard du
marché France/Tunisie : quadrant + position, `11–18 / 21–28 / 31–38 / 41–48` permanentes,
`51–55…` temporaires). Saisie en **chips** : on tape un numéro, il devient un chip
supprimable ; persistance en **chaîne séparée par virgules** (`"26, 27"`). Validation FDI
**souple** (suggestion, jamais bloquante : un praticien peut écrire `26 (MOD)`).

- *Évolution connue, reportée* : **odontogramme interactif** (schéma cliquable, faces
  M/D/O). Surdimensionné pour un outil de notes d'honoraires ; les chips FDI donnent
  l'essentiel (trace claire, futur « actes sur la dent 26 ») à coût minimal.
- *Alternative écartée* : table structurée `prestation_dents` — réservée au jour où des
  statistiques par dent seraient nécessaires (le texte virgulé suffit en v1).

### D11 — Note libre par acte
Champ **optionnel** `note` (texte multi-lignes) sur chaque prestation, pour une précision
clinique (« céramique pressée, teinte A2 »…). Sans effet sur la facturation.

### D12 — UI : carte d'acte réutilisable ; composer de plan en cartes
Un **composant « carte acte »** unique (libellé + prix + date + dents + note, avec
pré-remplissage référentiel) est réutilisé :

- en **dialogue d'ajout** d'un acte isolé (la carte + un sélecteur de plan « aucun ») ;
- empilé dans le **composer de plan** (titre + notes + cartes d'actes scrollables + total en
  direct), chaque carte portant un **bouton supprimer**, **un seul bouton « + Acte »**.

Édition en ligne compacte **écartée** : les cartes laissent la place au champ `note` et aux
dents. Réordonnancement par `sort_order` (glisser-déposer optionnel, *Open Decision*).

### D13 — Source unique du dû : la génération de document ne crée AUCUN paiement (RÉVISÉ ²)
Un montant dû est suivi à **un seul endroit**. Créer un **acte payant** ne crée **pas** de
ligne `paiements` : la **prestation est la créance** (dû + règlements). **Révision finale** : la
génération de document (y compris une note d'honoraires) ne crée **plus aucun** paiement —
la case « Créer un paiement en attente » a été **entièrement retirée** du dialogue (étapes
successives : `value=True` → OFF par défaut → supprimée). Le suivi de l'argent patient passe
**exclusivement** par les actes (créances) ; aucune fonctionnalité ne compte deux fois un même
montant, et il n'y a plus de chemin parallèle de création de dette via les documents.

### D15 — « Note d'honoraires » = bouton + dialogue dédié, filtré par catégorie de modèles
La génération d'une **note d'honoraires** est **extraite** dans un **bouton et un dialogue
dédiés** sur la fiche patient. Ce dialogue **ne propose que les modèles de la catégorie**
désignée comme « notes d'honoraires », tandis que la génération **générique** (« Générer un
document ») **exclut** cette catégorie (séparation nette). La catégorie cible est **configurable**
(réglage `meta` `note_honoraire_categorie`, choisi dans Paramétrage › Modèles parmi les
catégories existantes). Un **défaut conventionnel** « Notes d'honoraires » s'applique quand le
réglage n'est pas défini : ranger un modèle dans une catégorie ainsi nommée suffit, **sans
configuration préalable** (le réglage sert à pointer une autre catégorie). La comparaison de
catégorie est **tolérante** (espaces de bord + casse ignorés). Réutilise le **même moteur** de
génération (`_generate_dialog` paramétré par `category`) : pas de duplication, juste un filtrage
du catalogue de modèles et un titre adapté.

### D14 — Fiche patient : créances regroupées + historique des règlements unifié (RÉVISÉ)
> **Révision** (retour produit) : l'ancien bloc « Paiements » de la fiche, **désynchronisé**
> des lignes d'actes, est remplacé.

La fiche présente l'argent en **deux zones cohérentes** :

- **« Plans & actes »** = toutes les **créances** au même endroit : notes en attente, actes
  isolés, puis plans repliables. Le bouton **« Régler »** (cascade globale, D9) y figure dès
  qu'il reste à recouvrer.
- **« Règlements »** = l'**historique unifié des encaissements réels** (versements d'actes
  `prestation_reglements` **+** notes encaissées `paiements`), le plus récent d'abord, précédé
  d'un récap **Dû / Encaissé / Reste** consolidé (`solde_patient`). Chaque versement d'acte y
  apparaît : la zone est **synchronisée** avec les lignes d'actes.

## Risks / Trade-offs

- **Deux pistes d'argent patient** (`paiements` doc-based vs `prestations` acte-based). →
  *Mitigation* : périmètres distincts assumés en v1 ; la fiche patient regroupe les actes ;
  unification possible plus tard (D7).
- **Snapshot vs catalogue** (un prix de prestation qui « ne suit pas » le référentiel). →
  *Mitigation* : comportement voulu et documenté (D3).
- **Saisie des dents non normalisée** (texte libre toléré). → *Mitigation* : suggestion FDI
  + stockage virgulé cohérent ; structuration possible plus tard (D10).
- **Suppression d'un plan / d'un acte payé**. → *Mitigation* : règles D8 (détachement via
  `ON DELETE SET NULL`, interdiction si règlements).
- **Migration sur base de production**. → *Mitigation* : trois tables additives
  (`CREATE TABLE IF NOT EXISTS`), aucun `ALTER`/transform, snapshot pré-migration,
  anti-downgrade en place ; test sur copie réelle de `cabinet.db`.

## Migration Plan

1. **Schéma** : ajouter à `_SCHEMA` `plans_traitement`, `prestations` (colonnes `dents` et
   `note` nullable, **sans** colonne `type`), `prestation_reglements` (+ index sur
   `patient_id`, `plan_id`, `prestation_id`). Créées à l'ouverture par `executescript`.
   Aucune étape `_migrate()` de transformation requise. Bumper `SCHEMA_VERSION` 9 → 10.
2. **Sauvegarde** : snapshot pré-migration déclenché par `connect()` (mécanique existante).
3. **Déploiement** : nouvelle `.exe` à côté des données ; création transparente des tables ;
   `paiements` / `documents` / fichiers intacts.
4. **Rollback** : anti-downgrade (`SchemaTooNewError`) en place ; restaurer le snapshot au
   besoin. Aucune donnée détruite (additif).
5. **Validation pré-livraison** (manuelle) : copier un `cabinet.db` de `backups/`, lancer la
   build, vérifier le chargement intact ; créer un plan (cartes d'actes + un acte à 0) + un
   acte isolé, saisir des dents, régler partiellement, vérifier reste / progression / statut.

## Open Decisions

- **Odontogramme interactif** — *reporté* (D10). À rouvrir si la saisie visuelle par dent
  devient une demande forte.
- **Réordonnancement des actes d'un plan** — *proposé* : tri simple (`sort_order`) ;
  glisser-déposer optionnel plus tard.
