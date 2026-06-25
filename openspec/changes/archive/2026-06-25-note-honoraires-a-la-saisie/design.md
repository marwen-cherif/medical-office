## Context

Le flux actuel sépare deux gestes : créer un acte / un plan (`PrestationDialog`,
`PlanDialog` → hooks `useCreatePrestation` / `useCreatePlan` → routes
`POST /api/patients/{id}/prestations` et `/plans`), puis — séparément — générer la note
d'honoraires (`GenerateDialog` en mode `note`, ouvert depuis `PlansActesTab` via l'état
`noteIds` + la prop `initialSelection`). `GenerateDialog` sait déjà tout faire : choisir le
modèle, pré-cocher des actes passés par `initialSelection`, éditer les montants de note,
calculer les totaux, **générer** (route `POST …/documents/generate`, SSE) et **générer +
imprimer** via le drapeau `do_print` du payload `GenerateIn`. La règle métier
« note adossée à des actes ⇒ aucune créance créée » est déjà appliquée côté backend par
`generator.create_note_creance` (gating `has_actes`).

Le besoin est donc une **orchestration UI** : depuis la saisie, enchaîner vers cette fenêtre
de génération pré-remplie sur les actes qu'on vient de créer, sans dupliquer de logique ni
toucher au backend.

## Goals / Non-Goals

**Goals:**

- Offrir, en **création** d'acte et de plan, deux issues : « Enregistrer seulement » (défaut,
  inchangé) et « Enregistrer + générer la note ».
- Pour l'issue de génération, ouvrir `GenerateDialog` (mode `note`) **pré-coché avec
  exactement les actes nouvellement créés** ; le choix « générer » / « générer et imprimer » se
  fait dans cette fenêtre.
- Réutiliser tel quel le moteur existant (génération, impression `do_print`, règle de dette).
- Zéro nouveau réglage, zéro route, zéro migration.

**Non-Goals:**

- Pas de génération/impression **automatique sans confirmation** (l'issue ouvre la fenêtre ;
  l'utilisateur valide). On rejette donc explicitement le scénario « modèle par défaut +
  génération silencieuse ».
- Pas de prise en charge en **édition** (acte modifié, ajout d'acte sur plan existant).
- Pas de changement du **contrat de balises** ni du comportement de `facturation-multi-lignes`
  (la capability reste inchangée).

## Decisions

### D1 — Réutiliser `GenerateDialog` comme unique surface de génération

L'enchaînement **ouvre** la fenêtre existante au lieu d'appeler `generate` en arrière-plan.

- *Pourquoi* : garantit « aucune génération silencieuse », réutilise le choix de modèle, les
  montants de note éditables, les totaux, l'ajout d'actes à la volée, et la gestion d'erreur /
  progression SSE déjà en place. Aucune route ni réglage nouveau.
- *Alternative écartée* : générer directement via un « modèle de note par défaut » configuré.
  Rejetée — impose un nouveau réglage, échoue si le modèle réclame des champs à saisir
  (modèle mono-valeur), et masque la confirmation. (Choix utilisateur entériné.)

### D2 — Action à deux choix sur les fenêtres de saisie (deux boutons)

Le pied de fenêtre expose **deux boutons** : « Enregistrer » (action principale `type=submit`,
= enregistrer seulement, défaut inchangé, aussi déclenché par la touche Entrée) et
« Enregistrer + générer la note » (secondaire) qui enchaîne vers la génération.

- *Pourquoi* : conserve le geste par défaut intact tout en exposant l'enchaînement. Avec
  seulement **deux** issues, deux boutons sont plus simples — et plus robustes — qu'un menu
  déroulant : un menu **portalisé** dans une modale Radix est neutralisé par le piège à focus du
  `Dialog` (il ne s'affiche pas), travers connu du projet (cf. `Combobox`), qu'on évite ici.
- *Issue abandonnée* : « + générer et imprimer ». Le choix imprimer / ne pas imprimer se fait
  dans la fenêtre de note (boutons « Générer » / « Générer et imprimer »), inutile de le
  dupliquer à l'enregistrement.
- La validation des cartes d'acte est **factorisée** pour les deux issues (libellé/montant)
  afin que rien ne soit créé en cas d'erreur, quelle que soit l'issue.

### D3 — Remontée des `prestation_id` créés au parent + intention

Les fenêtres de saisie ne connaissent pas `GenerateDialog` ; c'est `PlansActesTab` qui
l'orchestre déjà (état `noteIds`). On ajoute donc un callback de fin de création :

- `PrestationDialog` (création) : à la réussite, appeler
  `onCreated?(prestationIds: number[], intent: "generate" | "print")` avec
  `prestationIds = [acteCréé.id]`.
- `PlanDialog` (création) : la boucle `createPrestation.mutateAsync(...)` **collecte les `id`
  retournés** ; à la fin, appeler `onCreated?(idsDesActesDuPlan, intent)`.
- `PlansActesTab` : sur ce callback, mémoriser l'intention puis `setNoteIds(prestationIds)`,
  ce qui ouvre `GenerateDialog` (mécanisme existant), en lui passant la nouvelle prop
  d'intention.

### D4 — Pré-cocher **seulement** les actes créés via `initialSelection`

`GenerateDialog`/`useGenerationForm` cochent par défaut **tous** les actes du patient (contrat
`facturation-multi-lignes`), mais **`initialSelection` restreint** la pré-sélection aux IDs
fournis. On passe donc `initialSelection = idsDesActesCréés` pour qu'**eux seuls** soient
cochés à l'ouverture (les actes préexistants restent décochés, l'utilisateur peut les cocher
s'il le souhaite).

- *Risque vérifié en tâche* : confirmer que `initialSelection` fourni l'emporte bien sur le
  « tout pré-coché » par défaut (cf. tasks — vérification manuelle avec un patient ayant des
  actes antérieurs).

### D5 — `GenerateDialog` inchangé côté actions (pas de prop `intent`)

`GenerateDialog` ne reçoit **aucune** prop d'intention : il expose comme avant « Générer » et
« Générer et imprimer », l'utilisateur choisit. Il pré-sélectionne déjà le modèle de note **si
un seul** est disponible (via `initialSelection`) et ne déclenche **jamais** la génération
automatiquement (respect de « aucune génération silencieuse »). L'idée initiale d'une prop
`intent` mettant en avant un bouton est **abandonnée** : la 3ᵉ issue ayant disparu, l'intention
ne portait plus aucune information utile.

### D6 — Backend et données inchangés

Aucune modification de `crm/routers/*`, `crm/generator.py`, du schéma ni de `SCHEMA_VERSION`.
Le payload `GenerateIn` (`selected_prestation_ids`, `do_print`) et la règle
`create_note_creance` (note adossée à des actes ⇒ pas de paiement) couvrent déjà le besoin,
sans double-comptage de la dette.

## Risks / Trade-offs

- **Le « tout pré-coché » par défaut prime sur `initialSelection`** → la note inclurait des
  actes non voulus. *Mitigation* : D4 + tâche de vérification explicite avec un patient ayant
  des actes antérieurs.
- **Plan créé sans aucun acte valide** avec une issue de génération → rien à facturer.
  *Mitigation* : si aucun acte n'a été créé, se rabattre sur « enregistrer seulement » et en
  informer l'utilisateur (toast), sans ouvrir de note vide.
- **Modèle mono-valeur sélectionné après l'enchaînement** (note à une seule ligne) → des
  champs peuvent rester à saisir. *Mitigation* : on **ouvre** la fenêtre (pas d'auto-submit),
  donc l'utilisateur complète puis valide ; la promesse « un clic » ne vaut que pour un modèle
  multi-lignes sans champ obligatoire.
- **Plusieurs modèles de note** disponibles → pas de pré-sélection, l'utilisateur choisit.
  *Trade-off* assumé : la validation « un clic » suppose un modèle unique.

## Migration Plan

Aucune migration de données ni de schéma. Changement **purement UI/React** ; déploiement par
remplacement du bundle. **Rollback** : revert des fichiers React modifiés (`PrestationDialog`,
`PlanDialog`, `PlansActesTab`, `GenerateDialog`) ; aucune trace persistée à nettoyer. Le client
TypeScript n'a pas besoin d'être régénéré (aucune évolution d'`openapi.json`).

## Open Questions

- Aucune bloquante. Le libellé exact du bouton « Enregistrer + générer la note » et un éventuel
  raccourci clavier sont tranchés à l'implémentation, sans impact sur la spec.
