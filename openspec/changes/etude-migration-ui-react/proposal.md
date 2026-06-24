## Why

L'interface du CRM est aujourd'hui écrite en **Flet** (Python) sous la forme d'un
**monolithe de 6320 lignes** (`crm/app.py`) : la maintenance et l'évolution sont
coûteuses, la qualité d'UI plafonne à ce que Flet expose, et l'application dépend d'un
framework Python de niche. Avant que ce monolithe ne grossisse davantage, on veut
**étudier objectivement** s'il faut migrer la seule couche UI vers **Flutter natif
(Dart)** — moteur métier Python inchangé — **et challenger Flutter face à React** plutôt
que de présupposer le vainqueur. Ce changement ne produit **aucun code applicatif** :
c'est une **étude de faisabilité** dont le livrable est une décision motivée.

## What Changes

- **Cartographier la surface UI actuelle** : écrans (Tableau de bord, Patients + fiche à
  onglets, Finances, Paramétrage, Travaux), composants récurrents (NavigationRail,
  calendriers, tableaux, dialogues) et **points de contact avec le moteur** Python.
- **Définir l'architecture cible** imposée par la contrainte Windows/Word COM : un
  **frontend Flutter (Dart)** dialoguant avec un **backend Python local** qui expose le
  moteur existant (`src/` + `crm/` hors `app.py`) via une **interface IPC** (à arbitrer :
  HTTP localhost, WebSocket, ou JSON-RPC sur stdio).
- **Comparer Flutter (Dart) vs React** (option desktop : Electron ou Tauri) selon une
  **grille de critères pondérés** : qualité/fluidité UI, maintenabilité, écosystème,
  intégration backend Python, packaging Windows + Word COM, courbe d'apprentissage,
  pérennité.
- **Établir le contrat d'interface UI ↔ moteur** (opérations exposées, formats d'échange,
  gestion des erreurs, opérations longues comme la génération Word) et vérifier qu'il
  **préserve les invariants** : Windows-only, idempotence par nom de fichier, préservation
  des données (`data/cabinet.db`, `output/`, `templates/`, `config.ini`).
- **Évaluer risques, effort et plan de migration incrémental** (écran par écran,
  cohabitation Flet/Flutter pendant la transition) et **émettre une recommandation**
  (migrer / ne pas migrer, et avec quelle techno).

> Hors périmètre de cette étude : tout portage de code réel d'écran (pas de POC), et tout
> chantier qui supprimerait Word COM (cible = **Windows desktop uniquement**).

## Capabilities

### New Capabilities
- `migration-ui-react` : exigences de l'**étude de faisabilité** de migration de la
  couche UI — livrables attendus, grille de comparaison Flutter vs React, contrat
  d'architecture cible (frontend découplé + backend Python local), contraintes à préserver,
  et format de la recommandation finale.

### Modified Capabilities
<!-- Aucune : une étude de faisabilité ne modifie pas les exigences métier existantes
     (fiche-patient, plans-de-traitement, etc.). Le portage éventuel de l'UI fera l'objet
     de changements ultérieurs, écran par écran. -->

## Impact

- **Code applicatif : aucun changement** dans ce périmètre. Seuls des artefacts d'étude
  sont produits sous `openspec/changes/etude-migration-ui-react/`.
- **Concerné à terme** (si l'étude conclut « migrer ») : `crm/app.py` (UI Flet), les
  lanceurs `crm_app.py` / `crm_web.py`, le build (`crm-desktop.spec`, `crm-web.spec`,
  `build-crm.bat`) et le packaging Windows. Le **moteur** (`src/`, `crm/db.py`,
  `crm/repo.py`, `crm/generator.py`, `crm/templates.py`, `crm/printing.py`,
  `crm/mailer.py`…) reste **inchangé** et devient une dépendance servie via IPC.
- **Dépendances potentielles futures à évaluer** : Flutter SDK / Dart, une couche IPC
  (serveur HTTP/WebSocket local ou JSON-RPC stdio côté Python), et l'outillage de build
  Flutter sous Windows. Aucune n'est ajoutée par cette étude.
