## Livrables de l'étude

Ce `design.md` porte les **décisions** (D1–D7) et l'analyse de fond. Il est complété par
quatre livrables consolidés dans le même dossier :

- `cartographie.md` — inventaire exhaustif des 14 écrans Flet, composants et appels moteur :
  **référentiel de complétude** opposable à la recette de parité (tâches 1.1–1.4).
- `facade-services.md` — **façade de services** backend (une opération par cas d'usage UI),
  contrat IPC (formats, codes d'erreur, progression) et **démonstration de préservation des
  invariants** (tâches 2.1, 2.2, 2.4).
- `risques-et-effort.md` — **registre des risques** (probabilité × impact × atténuation) et
  **estimation d'effort par lot** L0–L5 (tâches 4.1, 4.2).
- `tracabilite.md` — matrice **exigence → section** et verdict de complétude (tâche 6.1).

## Context

Le CRM est une application de bureau **Windows** pour un cabinet dentaire. L'UI est écrite
en **Flet** (Python) — un **monolithe de 6320 lignes** dans `crm/app.py` — et s'appuie sur
un **moteur métier Python** volontairement découplé de l'UI :

- `src/doc_filler.py` (remplissage `<TAG>` du `.docx` + export PDF via **Word COM**),
  `src/pdf_to_jpg.py` (PyMuPDF), `src/mailer.py` (Mailjet), `src/config.py`.
- `crm/db.py` (SQLite + migrations), `crm/repo.py` (CRUD, ~105 Ko), `crm/generator.py`
  (pont moteur), `crm/templates.py`, `crm/printing.py` (impression GDI), `crm/backup.py`.

Surface UI à reprendre : **Tableau de bord**, **Patients** (liste + fiche à onglets :
identité, actes/plans, documents, paiements, historique d'audit), **Finances** (paiements,
dépenses), **Paramétrage** (modèles, modèles mail, imprimante), **Travaux** (jobs,
prestataires). Composants transverses : `NavigationRail`, dialogues, calendriers
(simple + plage), tableaux groupés par catégorie, badges de statut Mailjet.

**Fait structurant** : *Flet est lui-même bâti sur Flutter* — il pilote des widgets Flutter
depuis Python. Migrer vers **Flutter natif (Dart)** n'est donc pas un changement de moteur
de rendu, mais un **changement de langage et de modèle d'exécution de l'UI**, qui **rompt le
lien direct UI → Python**. Or le moteur (Word COM, pywin32, Mailjet, PyMuPDF, SQLite) **doit
rester en Python** (cible = Windows desktop uniquement, Word COM obligatoire). Toute cible
non-Python pour l'UI impose donc une **frontière IPC** entre un frontend et un backend
Python local.

Objectifs portés par le demandeur : **indépendance vis-à-vis de Flet**, **maintenabilité**
(sortir du fichier unique), **qualité/fluidité d'UI**, et **comparer réellement Flutter et
React** plutôt que présupposer le gagnant.

## Goals / Non-Goals

**Goals :**
- Produire une **étude de faisabilité décisionnelle** : architecture cible, comparaison
  techno chiffrée, risques, effort, plan de migration, recommandation go/no-go.
- Garantir que la cible **réutilise le moteur Python sans le modifier** et **préserve tous
  les invariants** de `CLAUDE.md` (Word COM, idempotence par nom de fichier, préservation
  de `data/`, `output/`, `templates/`, `config.ini`, règles de migration de schéma).
- **Challenger Flutter vs React** sur une grille pondérée, traçable et reproductible.

**Non-Goals :**
- **Aucun code applicatif** ni POC dans ce périmètre (étude seule).
- **Pas de suppression de Word COM** ni de cible multi-plateforme (web/mobile) — explicitement
  hors sujet (Windows desktop only).
- Pas de refonte du moteur, du schéma SQLite, ni du format des `.docx`.
- Pas de changement du mode web actuel (Flet web) au-delà de constater son devenir.

## Decisions

### D1 — Architecture cible : frontend découplé + backend Python local (moteur inchangé)

Quel que soit le frontend retenu, l'architecture cible est **deux processus** sur la même
machine Windows :

```
┌─────────────────────────┐        IPC local         ┌──────────────────────────────┐
│  Frontend UI            │  ───────────────────────▶ │  Backend Python (sidecar)    │
│  (Flutter/Dart          │   requêtes / réponses      │  réutilise src/ + crm/*      │
│   ou React/TS)          │  ◀─────────────────────── │  (hors app.py)               │
│  écrans, navigation,    │   progression / events     │  Word COM, Mailjet, PyMuPDF, │
│  état local             │                            │  SQLite, impression GDI      │
└─────────────────────────┘                            └──────────────────────────────┘
```

- Le **backend** expose une **façade de services** (une fonction par cas d'usage UI :
  lister patients, générer une note, envoyer un mail, imprimer, etc.) qui appelle
  `crm/repo.py`, `crm/generator.py`, `crm/templates.py`, `crm/printing.py`, `src/mailer.py`.
  Le frontend ne contient **aucune logique métier**.
- Le backend reste **propriétaire des données** (`data/cabinet.db`, `output/`, `templates/`,
  `config.ini`) et continue d'appliquer backup au démarrage, migrations `_migrate()`,
  anti-downgrade `SCHEMA_VERSION`, idempotence par nom de fichier — **inchangés**.

**Alternatives écartées :**
- *Tout réécrire en Dart/TS (sans Python)* : impossible — Word COM/pywin32 n'existent pas
  hors Python ; réimplémenter la génération `.docx` sans Word est un autre projet (et
  contredit « Windows-only, Word COM »).
- *Rester sur Flet en le restructurant* (découper `app.py` en modules) : répond à la
  maintenabilité mais **pas** à l'indépendance vis-à-vis de Flet ni au plafond de qualité
  UI ; reste une option de repli légitime (cf. recommandation).
- *Embed d'un interpréteur Python dans le frontend* : complexité de packaging supérieure au
  sidecar, sans bénéfice ici.

### D2 — Comparaison Flutter vs React (grille recalibrée → recommandation React)

Deux familles évaluées : **Flutter (Dart)** compilé en exécutable Windows natif ; **React
(TypeScript)** empaqueté en desktop via **Electron** (Chromium + Node, mature, écosystème
maximal) ou **Tauri** (WebView2 + Rust, léger). Dans les deux familles, le **backend Python
sidecar est identique** (cf. D1) ; la comparaison porte sur le frontend et son intégration.

**Calibration (entrées du demandeur) :** mainteneur principal = **l'assistant IA** avec
**revue humaine en JS/TS** (pas un profil Flet/Dart) ; priorité explicite = **coût/vitesse
de mise en œuvre + écosystème** ; douleur principale avec Flet = **écosystème pauvre**. Ces
faits **annulent l'avantage « transfert Flet → Flutter »** d'un premier passage et
**alourdissent** les axes écosystème et vitesse.

> *Transparence :* un premier passage, sous l'hypothèse générique « équipe JS » et un fort
> bonus UI à Flutter, donnait un score serré (~73 % vs ~83 %). La correction de deux biais
> — UI pour un **CRM dense** (terrain web : TanStack Table/AG Grid > `DataTable` Flutter →
> égalité) et **profil réel du mainteneur** (l'avantage Flet→Flutter ne s'applique pas) —
> puis la calibration ci-dessous, creusent l'écart en faveur de React.

Pondérations (somme = 100), notes 0–5, score = note × poids :

| Critère | Poids | Flutter (Dart) | React (Tauri) |
|---|---:|---:|---:|
| Qualité d'UI (CRM dense : tableaux, formulaires) | 12 | 4 (48) | 4 (48) |
| Maintenabilité / structure | 18 | 4 (72) | 4 (72) |
| Écosystème / choix de librairies | 20 | 3 (60) | 5 (100) |
| Intégration backend Python local (sidecar + IPC) | 15 | 3 (45) | 4 (60) |
| Packaging Windows compatible Word COM | 12 | 4 (48) | 4 (48) |
| Vitesse/coût de mise en œuvre (libs + IA + familiarité TS) | 13 | 3 (39) | 5 (65) |
| Pérennité / risque techno | 10 | 4 (40) | 4 (40) |
| **Total** | **100** | **352 / 500 (~71 %)** | **433 / 500 (~87 %)** |

**Lecture :** sur ce contexte précis, React l'emporte **nettement**. L'écart vient
entièrement de deux axes — **écosystème** et **vitesse/coût** — que le demandeur valorise le
plus ; partout ailleurs (maintenabilité, qualité d'UI pour un CRM, packaging Windows,
pérennité) c'est **à égalité**, Word COM étant logé dans le sidecar Python commun aux deux.
Le seul avantage réel de Flutter ici (continuité du modèle de widgets Flet) **ne s'applique
pas** : le code est produit par l'IA et relu en JS/TS, pas écrit à la main par un profil Flet.

**Recommandation : migrer vers React, coquille Tauri.** Frontend **React (Vite +
TypeScript)**, backend **Python local en HTTP** (sidecar, moteur inchangé — cf. D1/D3),
empaqueté en desktop avec **Tauri** : binaire mince, **WebView2 déjà présent sous Windows 11**,
empreinte mémoire faible, et **sidecar Python natif** via la fonctionnalité `externalBin` de
Tauri (le binaire PyInstaller est déclaré comme ressource externe, lancé/arrêté par la
coquille Rust). Option la plus légère à garder en tête : servir le build React **directement
depuis le backend Python** et l'ouvrir dans le navigateur, comme le fait déjà `crm_web.py`.

> **Étude renommée** `etude-migration-ui-react` (dossier + capability `migration-ui-react`)
> pour refléter la conclusion ; l'objet reste le comparatif « migration de l'UI, Flutter
> *vs* React ».

**Alternative écartée dans la famille React : Electron.** Mature et à l'écosystème maximal,
mais binaire lourd (~150 Mo), empreinte mémoire élevée (Chromium embarqué) et redondant avec
le WebView2 déjà installé sous Windows 11. **Tauri** est préféré ici : il offre le même
modèle (React + sidecar Python) pour un livrable nettement plus léger, sans pénaliser la
vitesse de mise en œuvre. Electron resterait le repli si un besoin d'API Node natives
absentes de Tauri apparaissait.

### D3 — Canal IPC : HTTP localhost recommandé

| Canal | Pour | Contre |
|---|---|---|
| **HTTP localhost** (REST/JSON) | universel, trivial côté Dart **et** TS, debuggable, polling/SSE pour progression | port local à gérer (choisir un port libre, lier à 127.0.0.1) |
| **WebSocket** | bidirectionnel, idéal progression temps réel | un cran plus complexe ; surdimensionné pour la plupart des écrans |
| **JSON-RPC sur stdio** | pas de port réseau, couplage process direct | moins outillé, gestion manuelle du framing, multiplexage des appels concurrents |

**Décision : HTTP localhost** (127.0.0.1, port éphémère choisi par le backend et transmis
au frontend au démarrage), **complété d'un canal d'événements** (SSE ou WebSocket) pour la
**progression des opérations longues** : génération Word, envoi Mailjet (avec polling de
statut), impression. Les erreurs moteur (Word absent, COM en échec, Mailjet KO) sont
remontées en codes/messages structurés et présentées à l'utilisateur. Sécurité : liaison
**loopback uniquement**, jeton de session partagé frontend↔backend au lancement.

### D4 — Migration incrémentale avec cohabitation (pas de big-bang)

Le portage se fait **écran par écran**, l'ancienne UI Flet et la nouvelle UI coexistant le
temps de la transition. La frontière IPC (D1/D3) rend ça possible : le backend sert les deux.
Premier **écran pilote recommandé : Paramétrage** (périmètre restreint, peu de dépendances,
valide tout le tuyau IPC + packaging), puis un écran riche (**Patients**) pour éprouver
tableaux, fiche à onglets et opérations longues (génération/impression).

**Flet conservé comme oracle de référence.** La version Flet est gardée **intégralement**
pendant toute la migration : pour chaque écran, l'IA porte vers React **en s'inspirant de
l'implémentation Flet existante** (comportements, libellés FR, enchaînements de dialogues,
appels moteur), ce qui garantit la **parité fonctionnelle** sans re-spécifier chaque écran.
`crm/app.py` joue ainsi le rôle de spec exécutable. Flet n'est retiré qu'**après** portage du
dernier écran et **recette de parité** écran par écran. Les deux UI partageant le même backend
(D1), aucune divergence de données n'est possible pendant la cohabitation.

**Alternative écartée :** bascule en un bloc — risque trop élevé sur une app de production
mono-poste sans CI possible (génération exige Windows + Word).

### D5 — Packaging Windows

Le livrable reste **un exécutable double-cliquable**. Cible recommandée : frontend **React
empaqueté via Tauri** (`externalBin`) + **backend Python empaqueté via PyInstaller en sidecar**
(réutilise les specs existantes `crm-desktop.spec`), lancé par la coquille Tauri et arrêté
avec elle ; WebView2 est présent nativement sous Windows 11. Les données de l'utilisateur restent **à côté de l'exe** (`data/`, `output/`,
`templates/`, `config.ini`), exactement comme aujourd'hui. À documenter dans l'étude :
emplacement du sidecar, découverte du port, cycle de vie du process, et survie des données
entre mises à jour (règle « le `.exe` est remplaçable, les données vivent à côté »).

### D6 — Stack frontend React (Vite + Tailwind + shadcn/ui)

Socle retenu, optimisé pour un code **produit par l'IA** et **relu en TS**, et calé sur tes
écrans actuels :

- **React 19** + **Vite** (dernier stable, famille v7/v8 — à épingler selon compat Tauri /
  Tailwind v4 / shadcn à l'init) + **TypeScript**. Bundler **Rolldown** (Rust, VoidZero) à
  activer dès qu'il est stable dans Vite, pour des builds plus rapides (priorité vitesse).
- **Tailwind CSS v4** (config CSS-first `@theme`) + **shadcn/ui** : composants sur primitives
  **Radix**, **copiés dans le repo** → tu possèdes le code, pas de lib versionnée qui casse.
  Réponse directe à la douleur « écosystème pauvre de Flet » : écosystème immense *et*
  appropriation du code.
- **Correspondance avec l'existant** : `Table` (sur **TanStack Table**, listes denses),
  `Tabs` (fiche patient), `Dialog`/`Select`/`Command`, `Calendar` (**react-day-picker** →
  reprend les calendriers simple/plage), `Badge` (statuts Mailjet `opened/clicked/bounce`),
  `Sonner` (toasts), `Form` (**react-hook-form + zod**).
- **État serveur : TanStack Query** (cache, mutations, **polling du statut Mailjet**) au-dessus
  du client HTTP (D3/D7).
- **Thématisation par variables CSS** → reprise de la palette actuelle (tête de `crm/app.py`).

**Vite+ (commercial) écarté :** toolchain payante/early-access orientée monorepos
multi-paquets ; sur-dimensionnée pour une app unique. On reste sur l'OSS (Vite, **Vitest**,
**oxlint**/ESLint). À reconsidérer uniquement en cas de passage en monorepo.

**Alternatives kit UI :** **MUI** (continuité visuelle Material/Flet la plus douce, `MUI X
DataGrid` puissant, mais plus lourd/opinionné et code non possédé) ; **Mantine** (très complet
out-of-the-box, un cran moins « tu possèdes le code »). shadcn l'emporte sur appropriation +
AI-friendliness, qui sont les critères retenus.

**Points à verrouiller à l'init :** compat **Vite ↔ Tauri ↔ Tailwind v4 ↔ React 19 ↔ shadcn
CLI** (épingler des versions stables) ; discipline anti « class soup » (helper `cn()`,
extraction de composants) ; plafond data-grid (passer à AG Grid si un besoin de virtualisation
lourde émerge — improbable pour un cabinet unique).

### D7 — Service backend Python (FastAPI) + contrat typé

- **FastAPI retenu** (ASGI) expose la façade de services (D1) en **HTTP localhost** (D3) : `async`
  natif, **SSE/WebSocket** pour la progression des opérations longues (génération Word,
  polling Mailjet, impression), et **schéma OpenAPI** généré automatiquement.
- **Client TypeScript généré** depuis l'OpenAPI (`openapi-typescript` ou `orval`) → types
  **front ↔ back toujours synchrones**, levier majeur de fiabilité pour du code généré par
  l'IA et consommé par TanStack Query (D6).
- Réutilise le moteur (`crm/*`, `src/*`) **sans le modifier** ; empaqueté en sidecar via
  PyInstaller (D5).
- **Alternative écartée : Flask** (synchrone, SSE/progression moins naturels) — FastAPI préféré
  pour l'asynchrone et la génération OpenAPI.

## Risks / Trade-offs

- **Réécriture intégrale de l'UI (6320 lignes)** → migration **incrémentale** par écran avec
  cohabitation (D4) ; figer d'abord la cartographie comme référentiel de complétude.
- **Socle frontend entièrement nouveau (React/Tauri)** quel que soit le choix → réécriture
  par écran (D4) ; le code étant produit par l'IA et relu en JS/TS, le risque « langage » est
  faible, le risque résiduel porte surtout sur la frontière IPC et le packaging 2-process.
- **Frontière IPC = nouvelle source de pannes** (port occupé, sidecar mort, latence
  ressentie) → loopback + port éphémère + jeton ; superviser/redémarrer le sidecar ;
  mesurer la latence sur les écrans listes.
- **Opérations longues (Word COM, Mailjet, impression GDI)** mal rendues en asynchrone →
  canal d'événements dédié (D3), états de progression et d'erreur explicites dès le contrat.
- **Régression sur les invariants de données** (idempotence, migrations, backup) → ils
  restent **côté backend Python inchangé** ; l'étude doit le démontrer écran par écran.
- **Packaging plus complexe (2 process)** → réutiliser PyInstaller pour le sidecar ;
  documenter le cycle de vie ; recette manuelle obligatoire (Windows + Word, pas de CI).
- **Tauri ajoute une chaîne Rust + dépendance WebView2** à la construction → toolchain Rust
  sur le poste de build et présence de WebView2 (natif Win11) à vérifier ; Electron reste le
  repli si cette friction n'est pas souhaitée.
- **Sur-ingénierie** : si seule la maintenabilité compte, restructurer Flet (`app.py` en
  modules) coûte bien moins cher → garder cette option de repli explicite dans la reco.

## Migration Plan

1. **Cartographie** complète de l'UI Flet et des points de contact moteur (référentiel de
   complétude).
2. **Façade de services backend** spécifiée (contrat IPC : opérations, formats, erreurs,
   progression) — sans implémentation dans ce périmètre.
3. **Grille D2 calibrée** (pondérations validées avec le cabinet) + validation des
   hypothèses sensibles → **score final** et **recommandation go/no-go + techno**.
4. **Si go** : POC de l'écran pilote (Paramétrage) sur le tuyau IPC + packaging → changements
   ultérieurs, puis portage écran par écran (Patients, Finances, Travaux), Flet conservé en
   cohabitation jusqu'au dernier écran, puis retrait de Flet.
5. **Rollback** : tant que la cohabitation dure, l'UI Flet reste lançable ; abandonner la
   migration = continuer sur Flet sans perte (le backend Python n'a pas changé).

## Open Questions

- ~~Pondérations et techno~~ → **tranché** : priorité = coût/vitesse + écosystème, mainteneur
  = IA + revue JS/TS → **recommandation React** (cf. D2).
- ~~Coquille desktop~~ → **tranché : Tauri** (binaire léger, WebView2 natif Win11, sidecar
  Python via `externalBin`). Electron gardé en repli si besoin d'API Node natives.
- ~~Renommer l'étude~~ → **fait** : `etude-migration-ui-react` (dossier + capability).
- ~~Stack frontend & Vite+~~ → **tranché** (D6) : React 19 + Vite (stable) + Tailwind v4 +
  shadcn/ui + TanStack Query/Table ; **Vite+ écarté** (OSS suffisant).
- ~~POC séparé ?~~ → **résolu** : avec Flet gardé comme oracle de référence (D4), le **1er
  écran porté (Paramétrage) fait office de POC** (valide IPC + packaging). Pas de changement
  POC distinct.
- ~~Mode web Flet~~ → **tranché : reporter (porte ouverte)**. Cible immédiate = desktop Tauri ;
  avec FastAPI + React, re-servir l'UI en web/LAN plus tard est quasi gratuit — décision
  différée, non bloquante.
- ~~Framework backend~~ → **tranché : FastAPI** (D7).
- **Organisation du repo** (défaut proposé) : app React/Tauri dans `ui/`, service FastAPI en
  `crm/server.py` réutilisant `crm/*` sans le modifier — à confirmer à l'implémentation.
- Niveau d'exigence sur la **latence ressentie** des écrans listes via IPC (seuil acceptable)
  — à fixer comme critère de recette.
