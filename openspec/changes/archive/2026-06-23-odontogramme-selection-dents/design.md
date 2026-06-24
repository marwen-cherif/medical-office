## Context

La carte d'acte `_acte_card` (`crm/app.py`) expose un champ « Dents (FDI) » : on tape un
numéro, puis Entrée (`on_submit`) ou le bouton « + » crée un chip ; les chips sont
sérialisés en chaîne « 26, 27 » via `repo.normalize_dents` et persistés dans
`prestations.dents`. La validation FDI est volontairement **non bloquante** (la saisie
libre type « 26 (MOD) » est tolérée — voir le commentaire de `normalize_dents`).

Ce composant sert deux contextes : le **dialogue d'acte isolé** et le **composer de plan
de traitement**. Toute évolution doit donc se faire **dans `_acte_card`** pour bénéficier
aux deux, et fonctionner **à l'identique en desktop et en web** (même `crm/app.py`, le web
rendant côté serveur).

Contraintes structurantes du projet (CLAUDE.md) : **Windows uniquement** (génération Word
COM, hors sujet ici), **pas de migration** souhaitée pour ce changement, et préférence
forte pour **ne pas ajouter de dépendance** ni complexifier le build PyInstaller (deux
specs `crm-desktop.spec` / `crm-web.spec`).

La recherche d'une librairie d'odontogramme n'a trouvé que des solutions **hors stack** :
React/Vue (web JS, incompatible avec une UI Flet/Flutter) ou le paquet **Flutter
`teeth_selector`** (gère pourtant adulte + enfant, tap multi-sélection, notation ISO/FDI).
Aucune librairie Python/Flet n'existe.

## Goals / Non-Goals

**Goals:**

- Permettre d'**ajouter une dent sans validation explicite** : commit au fil de la
  frappe/dictée vocale, compatible avec la dictée du système (qui écrit dans le champ).
- Offrir un **odontogramme cliquable** adulte/enfant en notation FDI, sous le champ.
- Garder **une source de vérité unique** pour la sélection, synchronisée entre champ,
  chips et schéma (clic, re-clic, retrait chip, édition texte → état cohérent partout).
- Rester **purement additif** : format de persistance « 26, 27 » inchangé, validation FDI
  non bloquante conservée, champ texte + Entrée + « + » conservés, **zéro migration, zéro
  dépendance, zéro changement de build**.
- **Parité desktop / web** stricte.

**Non-Goals:**

- Pas de **reconnaissance vocale intégrée** : on s'appuie sur la dictée de l'OS qui remplit
  le champ focalisé ; aucune API micro, aucun service de transcription.
- Pas de **schéma anatomique réaliste** (surfaces dentaires MOD, faces, état carie/couronne,
  annotations cliniques par dent). L'odontogramme est un **sélecteur de numéros FDI**, pas
  un dossier parodontal.
- Pas de **changement du format persisté** ni de validation bloquante.
- Pas d'intégration du paquet Flutter `teeth_selector` (voir Décision 2).

## Decisions

### Décision 1 — Odontogramme **natif Flet** (grille de boutons-dents FDI)

L'odontogramme est construit en **contrôles Flet purs** : 4 quadrants disposés en croix
(maxillaire en haut, mandibulaire en bas ; droite patient à gauche de l'écran, gauche à
droite, convention clinique « face au patient »), chaque dent étant un petit
`Container`/bouton cliquable **affichant toujours son numéro FDI** ; la sélection se
distingue par un fond plein `NAVY` + numéro blanc (non sélectionnée : fond neutre + numéro
`NAVY`). Le composant expose un **handle** (`SimpleNamespace`) sur le modèle de
`_acte_card` : `.control`, `.refresh()` (re-rend selon la sélection), `.set_denture()`. La
sélection reste portée par `_acte_card` (source de vérité unique) ; le composant n'en est
qu'une vue, pilotée par les callbacks `is_selected` / `on_toggle`. **L'odontogramme est le
SEUL affichage de la sélection dans le formulaire** : pas de chips redondants (cf.
Décision 4).

- **Pourquoi** : aucune dépendance, aucun impact build, rendu **identique desktop/web**
  (Flet → Flutter des deux côtés), entièrement maîtrisé, FDI parfaitement explicite. La
  numérotation FDI est figée et triviale à générer par code.
- **Alternatives écartées** :
  - *Paquet Flutter `teeth_selector`* → exigerait de packager une **extension Flet**
    (paquet Flutter + bindings Python, build Flutter), ce qui casse la simplicité du build
    PyInstaller et ajoute une chaîne d'outils. Rejeté (cf. Décision 2).
  - *Librairie React/Vue (react-odontogram, odontograma)* → suppose un front web JS,
    **hors d'une app Flet**. Rejeté.
  - *Image SVG/PNG d'arcade avec zones cliquables* → la cartographie de zones dans Flet est
    fragile (pas de hit-test natif par zone) et non responsive. Rejeté au profit d'une
    grille de contrôles, plus simple et accessible.

### Décision 2 — Pas d'extension Flutter (rester en build PyInstaller pur Python)

Bien que `teeth_selector` couvre fonctionnellement le besoin (adulte + enfant), l'embarquer
imposerait une **extension Flet** compilée. Le projet se construit aujourd'hui en pur
Python via PyInstaller (`build-crm.bat`, deux specs) sans toolchain Flutter. Le surcoût
(maintenance, taille, build) est disproportionné face à une grille de boutons triviale.
**On s'inspire** de sa disposition et de sa notation, sans le code.

### Décision 3 — Saisie en bloc validée par Entrée (PAS de commit au fil de la frappe)

`add_dents_from_input` lit **tout** le champ, le découpe sur les séparateurs (`,` `;`
espace, saut de ligne), ajoute **tous** les numéros d'un coup (dédupliqués) et **vide le
champ**. Déclencheurs : `on_submit` (**Entrée**), le **bouton « + »** et `on_blur` (filet de
sécurité). **Aucun** `on_change` : rien n'est committé tant que l'utilisateur n'a pas validé.

- **Pourquoi Entrée et non au fil de la frappe** : besoin exprimé par l'utilisateur — on
  **dicte plusieurs dents enchaînées** (« 26 27 28 ») sans rien taper, puis **Entrée** les
  ajoute toutes. Un commit par séparateur au fil de la dictée était jugé prématuré et
  perturbait l'édition (réécriture du champ, position du curseur). L'approche bloc est plus
  simple, plus prévisible et sans interférence avec la dictée vocale de l'OS.
- **Tolérance saisie libre conservée** : un jeton non-FDI est accepté en chip —
  `normalize_dents` n'est pas durci. Il n'est simplement **pas reflété** sur le schéma
  (aucune dent ne s'y allume), ce qui est cohérent. Les séparateurs délimitant les jetons,
  un libellé multi-mots n'est pas un cas visé (cf. Non-Goals : surfaces MOD exclues).

### Décision 4 — **Source de vérité unique** ; pas de chips dans le formulaire

L'état de sélection reste la **liste `dents_list`** déjà présente dans `_acte_card`. Le
formulaire n'affiche **pas** de chips (« tags » verts) — jugés inutiles et redondants par
l'utilisateur. Les deux seules vues sont :

- *Champ* (ajout) : l'ajout en bloc (Décision 3) étend `dents_list` à la validation.
- *Odontogramme* (affichage **et** sélection) : un **clic** sur une dent toggle son état ;
  c'est aussi là qu'on **retire** une dent (re-clic), à la place de l'ancienne croix de chip.
- À chaque mutation : `sync()` ré-appelle `odonto.refresh()` pour refléter l'état.

`read()` continue de renvoyer `", ".join(dents_list)` ⇒ **persistance inchangée**.

> **Limite assumée** : un jeton **non FDI** ajouté via le champ (ex. « 19 ») est persisté
> mais **non affichable** sur le schéma — donc invisible dans le formulaire désormais
> centré sur l'odontogramme. Cas marginal (validation FDI non bloquante) ; à rouvrir si la
> saisie libre devient un besoin réel.

### Décision 5 — Denture adulte/enfant : défaut par âge, basculable

Helpers FDI **purs** ajoutés dans `crm/repo.py` : ensembles `DENTS_PERMANENTES` (11–18,
21–28, 31–38, 41–48) et `DENTS_TEMPORAIRES` (51–55, 61–65, 71–75, 81–85), plus
`fdi_quadrant(num)` / `is_fdi_valide(num)`. L'odontogramme choisit la denture par
défaut **selon l'âge** : si la **date de naissance** est connue et l'âge < ~13 ans, défaut
denture **temporaire (enfant)** ; **sinon — y compris quand la naissance n'est pas
renseignée — défaut denture permanente (adulte)**. Un **sélecteur** (segmenté
ou onglets) bascule manuellement adulte/enfant à tout moment ; les dents déjà retenues d'un
type restent en chips même quand l'autre denture est affichée.

- **Pourquoi dans `repo.py`** : c'est de la logique métier pure (testable, sans Flet),
  réutilisable, et `normalize_dents` y vit déjà. Aucune table, aucune migration.

### Décision 6 — Intégration dans `_acte_card` (un seul point)

Le composant est inséré **sous** la `Row` champ + « + » et la `chips_row` existantes, dans
la `Column` de la carte. Comme `_acte_card` est l'unique brique d'acte, le dialogue isolé
**et** le composer de plan en héritent sans duplication. Aucun changement de signature
publique de `_acte_card` (le handle reste compatible).

## Risks / Trade-offs

- **[Dictée vocale mal segmentée par l'OS]** → l'ajout se fait sur **tout le champ à la
  validation** (Entrée/« + »/blur) en découpant sur les séparateurs ; rien n'est committé au
  fil de la frappe, donc pas de réécriture intempestive du champ. Comportement à **valider
  manuellement** au fauteuil (pas de CI possible).
- **[`on_blur` committe au mauvais moment]** → le filet `on_blur` ajoute le contenu restant
  quand le focus quitte le champ (ex. clic sur le schéma) ; c'est voulu (on ne perd pas une
  dictée non validée) et sans effet si le champ est vide.
- **[Encombrement vertical de l'odontogramme dans le dialogue]** → grille **compacte**
  (boutons-dents petits, quadrants serrés), repliable si nécessaire ; la carte d'acte est
  déjà scrollable dans son dialogue.
- **[Parité web : clics et focus]** → composant 100 % Flet (aucun widget natif) ⇒ rendu et
  événements identiques ; à **vérifier en mode web** (`python crm_web.py`).
- **[Confusion gauche/droite de l'arcade]** → adopter la **convention clinique** (vue face
  au patient : sa droite à gauche de l'écran) et libeller les côtés, comme `teeth_selector`.
- **[Régression de la persistance]** → `read()` et `normalize_dents` **inchangés** ;
  `prestations.dents` garde « 26, 27 ». Aucun risque de migration.

## Migration Plan

Aucune migration de schéma ni de données (`SCHEMA_VERSION` inchangé). Changement
**purement additif et UI**. Déploiement = remplacement de l'`.exe` habituel ; les données
existantes (`prestations.dents`) restent lues/écrites au format actuel. Rollback =
réinstaller l'`.exe` précédent (aucun effet sur la base).

## Open Questions

- *(Tranché)* **Défaut adulte/enfant** : **auto selon l'âge**, adulte par défaut si la date
  de naissance n'est pas renseignée. Bascule manuelle toujours possible. Pas de vue mixte
  au premier jet.
- *(Tranché)* **Mode de validation du champ** : **ajout en bloc à Entrée** (+ « + » et
  blur), **pas** de commit au fil de la frappe. On dicte plusieurs dents enchaînées puis on
  valide.
- *(Tranché)* **Étiquettes de l'odontogramme** : le numéro FDI reste **toujours visible**
  sur chaque dent (sélectionnée ou non) ; la sélection se distingue par le fond plein.
- *(Tranché)* **Chips dans le formulaire** : **supprimés** — jugés inutiles ; la sélection
  est lue/modifiée directement sur l'odontogramme. (Les badges de dents de la fiche patient,
  hors formulaire, restent inchangés.)
- **Seuil d'âge exact** (≈ 13 ans) pour basculer en denture enfant : à confirmer à l'usage
  (sans impact sur le contrat de la capability).
