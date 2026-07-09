## 1. Orchestration dans `PlansActesTab`

- [x] 1.1 Aucun état d'intention nécessaire : l'état `noteIds` (déjà présent) suffit — non nul, il ouvre `GenerateDialog`. Le choix imprimer / ne pas imprimer se fait dans la fenêtre de note.
- [x] 1.2 Écrire un handler `onActesCreated(prestationIds: number[])` qui, si `prestationIds` est non vide, ouvre `GenerateDialog` via `setNoteIds(prestationIds)` ; sinon n'ouvre rien (cf. design, plan sans acte ⇒ toast « Plan créé » côté dialogue).
- [x] 1.3 Passer ce handler à `PrestationDialog` et `PlanDialog` (uniquement en mode création).
- [x] 1.4 Réinitialiser `noteIds` à la fermeture de `GenerateDialog` (à côté de `exitSelect()`).

## 2. Action à deux choix dans `PrestationDialog` (création)

- [x] 2.1 Factoriser la validation de la carte d'acte (libellé obligatoire, montant valide) — `validateActe` — exécutée avant création quelle que soit l'issue ; bloque sans rien créer en cas d'erreur.
- [x] 2.2 Remplacer le bouton unique par **deux boutons** : « Enregistrer » (= enregistrer seulement, `type=submit`, inchangé) + « Enregistrer + générer la note ». Affichés uniquement en **création** (pas en édition). Pas de menu déroulant (un menu portalisé est neutralisé par le piège à focus de la modale).
- [x] 2.3 Sur l'issue de génération : après succès de `create.mutate`, récupérer l'`id` de l'acte créé et appeler `onCreated?.([id])` ; sur « enregistrer seulement », conserver le `onClose()` actuel.

## 3. Action à deux choix dans `PlanDialog` (création)

- [x] 3.1 Dans `submit()`, collecter les `id` retournés par chaque `createPrestation.mutateAsync(...)` de la boucle d'actes du plan dans un tableau `createdIds`.
- [x] 3.2 Ajouter les mêmes deux boutons (« Enregistrer » / « + générer la note »), réservés à la **création** du plan, partageant la validation des cartes d'acte.
- [x] 3.3 Sur l'issue de génération : à la fin de la création, appeler `onCreated?.(createdIds)` (et se rabattre sur « enregistrer seulement » + toast si `createdIds` est vide) ; sinon `onClose()` comme aujourd'hui.

## 4. `GenerateDialog` : pré-remplissage (sans prop d'intention)

- [x] 4.1 `GenerateDialog` n'a **pas** de prop d'intention : il expose « Générer » et « Générer et imprimer » et l'utilisateur choisit dans la fenêtre.
- [x] 4.2 (Abandonné) Mise en avant d'un bouton selon l'intention — supprimée avec la 3ᵉ issue « + générer et imprimer ».
- [x] 4.3 Quand un **seul** modèle de note est disponible, il est pré-sélectionné (via `initialSelection`) ; la génération n'est **jamais** déclenchée automatiquement (aucune génération silencieuse).
- [x] 4.4 Vérifier que la pré-sélection des actes utilise bien `initialSelection` (les actes créés) et n'hérite pas du « tout pré-coché » par défaut.

## 5. Vérification manuelle (Windows + Word requis)

- [x] 5.1 Acte unique : « Enregistrer + générer » ouvre la note avec ce seul acte pré-coché ; générer produit une note à une ligne, sans créance distincte (dette = montant de l'acte, une seule fois).
- [x] 5.2 Plan + 3 actes : « Enregistrer + générer » ouvre la note avec exactement ces 3 actes pré-cochés (aucun acte antérieur du patient coché).
- [x] 5.3 Patient avec actes antérieurs : confirmer que seuls les actes nouvellement créés sont cochés (validation de D4).
- [x] 5.4 Dans la fenêtre de note : cliquer « Générer » (sans imprimer) génère sans envoyer à l'imprimante ; cliquer « Générer et imprimer » imprime sur l'imprimante configurée.
- [x] 5.5 « Enregistrer seulement » : comportement strictement identique à l'existant (aucune note).
- [x] 5.6 Abandon : créer via « + générer » puis fermer la note sans générer ⇒ le(s) acte(s) restent listés dans l'onglet Actes/Plans, aucune note produite.

## 6. Clôture

- [x] 6.1 `openspec validate note-honoraires-a-la-saisie --strict` passe sans erreur.
- [x] 6.2 Mettre à jour la mémoire projet si une décision durable mérite d'être retenue (sinon, ne rien ajouter).
