## 1. Backend — moteur de génération

- [x] 1.1 Dans `crm/generator.py`, étendre `create_note_creance` avec les paramètres
  `track: bool = True` et `montant_override: float | None = None` : no-op si `not track` ;
  montant effectif = `montant_override` si fourni sinon `document.montant` ; conserver les
  gates existants (`is_note`, `has_actes`/autonome, montant `> 0`, idempotence par
  `document_id`) ; créer le `paiement` avec le montant effectif et journaliser le montant réel.
- [x] 1.2 Mettre à jour la docstring de `create_note_creance` (option de suivi + montant
  surchargeable indépendant de l'affichage du document).

## 2. Backend — API (router documents)

- [x] 2.1 Dans `crm/routers/documents.py`, ajouter à `DraftIn` les champs
  `tracer_creance: bool = True` et `montant_creance: float | None = None` (hérités par
  `GenerateIn`), avec commentaire « défaut = comportement actuel, lus seulement à la génération ».
- [x] 2.2 Dans la route `generate`, transmettre `track=body.tracer_creance` et
  `montant_override=body.montant_creance` à `create_note_creance` (laisser `_persist_draft` les
  ignorer).
- [x] 2.3 Vérifier que les modèles Pydantic n'imposent pas `extra="forbid"` (sinon adapter) pour
  ne pas casser un client non régénéré. → Aucun `extra="forbid"`/`model_config` dans `crm/` :
  Pydantic ignore les champs inconnus par défaut, rien à modifier.

## 3. Frontend — dialogue de génération

- [x] 3.1 Dans `ui/src/screens/patient-detail/GenerateDialog.tsx`, ajouter l'état local
  `tracerCreance` (défaut `true`) et `montantCreance` (chaîne).
- [x] 3.2 À l'initialisation des champs mono (effet sur `form.data`), pré-remplir `montantCreance`
  depuis la valeur de la balise montant du modèle (`<MONTANT>`/`<PRIX>`/`<TARIF>`) et remettre
  `tracerCreance` à `true`. → `montantCreance=null` ⇒ suit le montant du document (`docMontantStr`)
  jusqu'à édition (découplage), `tracerCreance=true`.
- [x] 3.3 Afficher, dans la branche mono-valeur, un bloc **case à cocher + champ montant**
  **seulement si** `mode === "note"` ∧ `!form.data.is_multiligne` ∧ note autonome
  (`singleActeId == null`) ; le champ montant n'apparaît que si la case est cochée.
- [x] 3.4 Dans `buildBody` (branche mono), inclure `tracer_creance` et `montant_creance`
  (parse virgule/point ; envoyer `null` si vide). → `null` quand non édité ⇒ backend retombe
  sur `document.montant`.

## 4. Génération du client et vérification

- [x] 4.1 Régénérer l'OpenAPI + le client TypeScript (`ui/src/api/schema.d.ts`, `types.ts`) selon
  la procédure du dépôt, et confirmer que `buildBody` reste typé. → OpenAPI re-dumpé
  (`tracer_creance`/`montant_creance` présents), `npm run gen:api` OK, `types.ts` ré-exporte
  `S["DraftIn"]`/`S["GenerateIn"]` (aucune édition), `npm run typecheck` passe.
- [x] 4.2 Vérification de la logique de créance (scénarios a–e + no-op f/g/h) faite
  **programmatiquement** sur une base temporaire : (a) défaut → créance 300 ; (b) décoché →
  aucune ; (c) override 200 → créance 200, document inchangé ; (d) montant nul → aucune ;
  (e) régénération → pas de 2ᵉ créance ; (f) `has_actes`, (g) multi-lignes, (h) non-note → aucune.
  **Reste un gate manuel pré-livraison** (Windows + Word, pas de CI — cf. CLAUDE.md) : rendu
  Word réel + parcours UI du bloc case/montant.
