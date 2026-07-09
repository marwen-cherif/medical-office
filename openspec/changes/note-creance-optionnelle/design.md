## Context

La règle « source unique du dû » (`plans-de-traitement`) impose qu'une **note d'honoraires
autonome** (mono-valeur, sans acte rattaché) crée **toujours** une créance « note » à la
génération. Cette logique vit dans `generator.create_note_creance` (`crm/generator.py`), appelée
par la route `POST /patients/{id}/documents/generate` (`crm/routers/documents.py`). Le gating
actuel est : `is_note` ∧ note autonome (`is_note_autonome`, i.e. pas de `__lignes__` ∧ pas
d'acte transmis via `has_actes`) ∧ `document.montant > 0` ∧ aucun paiement déjà rattaché au
document (idempotence par `document_id`). Le montant de la créance = `document.montant`, dérivé
de la balise `<MONTANT>`/`<PRIX>`/`<TARIF>` saisie dans le modèle mono-valeur.

Côté UI, le dialogue `GenerateDialog.tsx` distingue déjà : modèle **multi-lignes** (sélection
d'actes + montants de note éditables) vs **mono-valeur** (champs dynamiques). Une note mono-valeur
**générée depuis un acte unique** (`singleActeId`) est transmise comme adossée
(`selected_prestation_ids`) et ne crée donc pas de créance.

L'utilisateur veut pouvoir, à la génération d'une note **autonome mono-valeur**, **choisir** si la
note est suivie comme créance en attente, et avec **quel montant** — indépendamment du montant
imprimé.

## Goals / Non-Goals

**Goals:**
- Exposer à la génération, pour une note **autonome mono-valeur** uniquement, une **case à cocher
  « Tracer la note en attente (créance) »**, **cochée par défaut** (comportement actuel préservé).
- Quand la case est cochée, afficher un **champ « Montant à suivre »** pré-rempli avec le montant
  du document, **indépendant** du montant rendu/imprimé.
- Quand la case est décochée, générer la note **sans** créance.
- Rester **rétro-compatible** sans interaction (défaut = ancien comportement) et **sans migration**
  de schéma SQLite.

**Non-Goals:**
- **Notes multi-lignes** : aucun changement (le dû y est porté par les actes). Le suivi optionnel
  pour ce cas fera l'objet d'une **spec ultérieure** (cf. Open Questions).
- Note mono-valeur **générée depuis un acte** : reste adossée (pas de créance), inchangée.
- Modifier le moteur partagé `src/`, le schéma de la base, ou la sémantique des créances déjà
  existantes (une créance créée reste indépendante : régénérer/supprimer la note ne la touche pas).

## Decisions

### D1 — Deux champs portés par le corps de génération, pas par le brouillon
`DraftIn` (donc `GenerateIn` qui en hérite) reçoit deux champs optionnels :
- `tracer_creance: bool = True` — l'utilisateur veut-il créer la créance ?
- `montant_creance: float | None = None` — montant de la créance ; `None` ⇒ retombe sur
  `document.montant`.

Le défaut `True`/`None` rend tout client existant et tout appel sans ces champs **identique** à
l'actuel. Ils ne sont **lus qu'au flux `generate`** ; `_persist_draft` les ignore.

**Pourquoi ne pas persister le choix dans le brouillon ?** La créance n'est créée qu'à la
génération, et une fois créée elle est **indépendante** et stockée dans `paiements`
(idempotence par `document_id`). Le choix n'a donc d'effet qu'à la **première** génération ;
le persister dans `documents.variables` ajouterait un état sans valeur (et brouillerait le
contrat `__lignes__`). On re-propose simplement les défauts (coché, montant du document) à
chaque ouverture. *Alternative écartée :* stocker le choix dans `variables` — rejetée pour
éviter un état superflu et toute interaction avec la clé réservée `__lignes__`.

### D2 — Gating étendu dans `create_note_creance`, montant découplé
`create_note_creance(conn, document, *, is_note, has_actes=False, track=True,
montant_override=None)` :
1. inchangé : no-op si `not is_note`, si `has_actes`, ou si la note n'est pas autonome ;
2. **nouveau** : no-op si `not track` ;
3. **montant effectif** = `montant_override` s'il est fourni, sinon `document.montant` ;
4. inchangé : no-op si montant effectif `<= 0`, ou si une créance est déjà rattachée au document
   (idempotence) ;
5. crée le `paiement` en_attente avec le **montant effectif**.

Le découplage montant créance ↔ `document.montant` est ainsi confiné à `create_note_creance` :
le rendu du document (`render_document`, balises `<MONTANT>`/`<TOTAL>`) ne voit jamais
`montant_creance`. *Alternative écartée :* faire piloter `document.montant` par le champ — rejetée
car l'utilisateur a explicitement demandé un montant de créance **indépendant** de l'affichage.

### D3 — UI : bloc conditionnel dans la branche mono-valeur de `GenerateDialog`
Le bloc (case + champ montant) s'affiche **seulement si** : `mode === "note"` ∧
`form.data && !form.data.is_multiligne` ∧ note **autonome** (`singleActeId == null`). Pour une note
mono générée depuis un acte, le backend la traite déjà comme adossée — le bloc n'a pas de sens et
reste masqué.

État local : `tracerCreance` (défaut `true`) et `montantCreance` (chaîne). Le champ montant est
**pré-rempli** à l'initialisation des champs mono à partir de la valeur de la balise montant du
modèle (`<MONTANT>`/`<PRIX>`/`<TARIF>`). Étant **indépendant**, il ne se resynchronise pas
automatiquement si l'utilisateur modifie ensuite la balise montant du document (cohérent avec la
décision « montant indépendant »). `buildBody` (branche mono) ajoute
`tracer_creance: tracerCreance` et `montant_creance: parse(montantCreance)`.

### D4 — Régénération du client TypeScript
L'ajout des champs au modèle Pydantic change l'OpenAPI : régénérer `ui/src/api/schema.d.ts` et
`types.ts` selon la procédure du dépôt (cf. mémoire migration React) pour que `buildBody` reste
typé.

## Risks / Trade-offs

- **[Champ montant non resynchronisé après édition de la balise document]** → comportement
  **voulu** (montant indépendant) ; pré-remplissage initial suffisant. Mitigation : libellé clair
  « Montant à suivre » distinct du montant du document.
- **[Client TS oublié]** → `buildBody` enverrait des champs non typés et le défaut backend
  s'appliquerait (créance créée) : pas de régression de données, mais l'option serait inopérante.
  Mitigation : tâche explicite de régénération + vérification manuelle.
- **[Pydantic `extra="forbid"`]** → si les modèles refusaient les champs inconnus, un client non
  régénéré échouerait. Mitigation : ajouter les champs **dans `DraftIn`** (hérité par `GenerateIn`)
  plutôt que de compter sur la tolérance aux extras.
- **[Confusion utilisateur entre montant affiché et montant suivi]** → deux montants peuvent
  diverger. Mitigation : pré-remplissage au montant du document (cas nominal : identiques) et
  intitulé explicite.

## Open Questions

- **Notes multi-lignes (reporté à une autre spec)** : transposer un suivi optionnel au multi-lignes
  est non trivial car le dû y est déjà porté par les actes (existants + nouveaux créés comme
  prestations). Trois pistes identifiées, à arbitrer dans une spec dédiée : (a) ne rien changer ;
  (b) une case qui empêche la **création en dette des nouveaux actes** (rompt « pas de ligne libre
  non tracée ») ; (c) un mode « note informative » ne persistant **aucune** dette. Décision
  explicite de l'utilisateur : **hors scope ici**.
