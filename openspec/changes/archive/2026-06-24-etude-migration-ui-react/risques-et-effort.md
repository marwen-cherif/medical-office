# Registre des risques & estimation d'effort

> **Rôle de ce document (tâches 4.1, 4.2).** Formalise en **registre structuré**
> (probabilité × impact × atténuation) les risques esquissés dans `design.md` (section
> *Risks / Trade-offs*), et fournit une **estimation d'effort par lot** exploitable pour la
> décision go/no-go. Échelles : probabilité **F**(aible) / **M**(oyenne) / **É**(levée),
> impact idem. L'effort est exprimé en **ordres de grandeur assumés** (le mainteneur principal
> étant l'assistant IA avec revue humaine JS/TS — cf. `design.md` D2) ; ce ne sont pas des
> jours-homme classiques mais des **fourchettes relatives comparables d'un lot à l'autre**.

## 1. Registre des risques (tâche 4.1)

| # | Risque | Prob. | Impact | Atténuation |
|---|---|:--:|:--:|---|
| R1 | **Réécriture intégrale de l'UI** (6320 lignes, 14 écrans) — périmètre sous-estimé | É | É | Migration **incrémentale** par écran + cohabitation (`design.md` D4) ; `cartographie.md` gelée comme **référentiel de complétude** ; Flet conservé en **oracle de parité**. |
| R2 | **Frontière IPC = nouvelle source de pannes** (port occupé, sidecar mort, jeton) | M | É | Loopback + **port éphémère** + jeton de session ; superviser/redémarrer le sidecar depuis la coquille Tauri ; *health-check* au lancement. |
| R3 | **Latence ressentie** sur écrans listes via HTTP localhost | M | M | Cache + pagination déjà en place (`PAGE_SIZE`) ; TanStack Query (cache/prefetch) ; **mesurer** sur Patients/Documents et fixer un seuil de recette (tâche 3.3). |
| R4 | **Opérations longues mal rendues** en asynchrone (Word COM, Mailjet, GDI) | M | É | Canal d'événements dédié (SSE/WS, `design.md` D3 / `facade-services.md` §4) ; états progression + erreur explicites dès le contrat ; **COM initialisé dans le thread worker**. |
| R5 | **Régression sur les invariants de données** (idempotence, migrations, backup, snapshots) | F | É | Invariants **côté backend Python inchangé** (`facade-services.md` §6) ; recette de parité écran par écran ; test sur **vraie DB** de `backups/` (règle `CLAUDE.md` #7). |
| R6 | **Packaging 2 process** plus complexe (sidecar + découverte du port + cycle de vie) | M | M | Réutiliser PyInstaller (`crm-desktop.spec`) pour le sidecar ; `externalBin` Tauri ; documenter lancement/arrêt ; **recette manuelle** obligatoire (Windows + Word, pas de CI). |
| R7 | **Chaîne de build Tauri** (toolchain Rust + dépendance WebView2) | M | M | WebView2 **natif Win11** (vérifier) ; toolchain Rust sur le poste de build seulement ; **Electron en repli** documenté si friction. |
| R8 | **Composants sur mesure** non couverts par les libs (odontogramme FDI, carte d'acte, donuts) | M | M | Identifiés dans `cartographie.md` §3 comme **à reconstruire** ; portés en priorité avec l'écran Patients (pilote n°2) ; Flet comme spec exécutable. |
| R9 | **Dérive de « class soup » Tailwind** / code généré peu maintenable | M | M | Discipline `cn()`, extraction de composants, shadcn (code possédé), revue humaine JS/TS (`design.md` D6). |
| R10 | **Incompatibilités de versions** (Vite ↔ Tauri ↔ Tailwind v4 ↔ React 19 ↔ shadcn CLI) | M | M | **Épingler** des versions stables à l'init (`design.md` D6) ; valider la chaîne sur l'écran pilote avant d'industrialiser. |
| R11 | **Sur-ingénierie** si seule la maintenabilité comptait | F | M | Option de repli explicite : restructurer Flet (`app.py` en modules) — gardée dans la reco (`design.md`). |
| R12 | **Divergence de données** pendant la cohabitation Flet/React | F | É | **Backend unique partagé** par les deux UI (`design.md` D1) ⇒ divergence structurellement impossible. |

**Risques majeurs** (impact É) : R1, R2, R4, R5, R12 — tous adressés par les décisions D1/D3/D4.
Le profil de risque résiduel se concentre sur la **frontière IPC et le packaging 2 process**
(R2, R4, R6, R7), validés en bloc par l'**écran pilote** Paramétrage (`design.md` D4).

## 2. Estimation d'effort par lot (tâche 4.2)

| Lot | Contenu | Effort | Commentaire |
|---|---|:--:|---|
| L0 — **Socle backend (FastAPI)** | `crm/server.py` : façade de services (`facade-services.md` §2), schéma OpenAPI, jeton + port éphémère, canal d'événements SSE, workers pour opérations longues | **M** | Réutilise le moteur **sans le modifier** ; l'essentiel est de l'**adaptation**, pas de la logique métier. |
| L1 — **Socle frontend** | Vite + React 19 + TS + Tailwind v4 + shadcn, shell + NavigationRail, client TS généré + TanStack Query, thème (palette), composants transverses (Table/Tabs/Dialog/Calendar/Badge) | **M→É** | Coût **unique** ; débloque tous les écrans. Calendriers FR et tableaux denses inclus. |
| L2 — **Tuyau IPC + packaging pilote** | Tauri `externalBin` + sidecar PyInstaller, découverte du port, cycle de vie, **écran pilote Paramétrage** porté de bout en bout | **M** | Valide R2/R4/R6/R7/R10 sur un périmètre restreint **avant** d'industrialiser. |
| L3 — **Écran riche Patients** | Liste + fiche à onglets, **odontogramme**, **carte d'acte**, opérations longues (génération/impression), historique | **É** | Écran le plus dense ; éprouve les composants sur mesure (R8) et le canal d'événements (R4). |
| L4 — **Reste des écrans** | Tableau de bord (+ donuts), Finances (paiements/dépenses), Travaux (documents/jobs/détail), Prestataires | **É** | Volume réparti ; chaque écran porté **en s'inspirant du Flet** (oracle de parité). |
| L5 — **Recette de parité + retrait de Flet** | Vérification écran par écran contre `cartographie.md`, test sur vraie DB, suppression de `crm/app.py` et des lanceurs Flet | **M** | Gate manuel (Windows + Word) ; Flet retiré **seulement après** parité complète. |

**Lecture.** Le coût est dominé par **L1 (socle frontend)** et **L3/L4 (portage des écrans
denses)**. L0/L2 sont des coûts de mise en place modérés **non récurrents** ; le code étant
produit par l'IA et relu en JS/TS, le risque « langage » est faible et l'effort marginal par
écran **décroît** une fois le socle + le pilote validés. La **séquence L0 → L2 (pilote) → L3
… → L5** permet un **go/no-go intermédiaire** après le pilote, avant d'engager le gros du
portage (L3/L4).
