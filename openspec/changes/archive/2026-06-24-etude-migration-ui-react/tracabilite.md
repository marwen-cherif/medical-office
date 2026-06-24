# Traçabilité — exigences `migration-ui-react` → livrable

> **Rôle de ce document (tâche 6.1).** Vérifie que **chaque exigence** du spec
> `specs/migration-ui-react/spec.md` (et chacun de ses scénarios) est **couverte** par au moins
> une section du livrable de l'étude. Sert de checklist de revue finale (tâche 6.2, à acter
> avec le demandeur). Fichiers du livrable : `proposal.md`, `design.md`, `cartographie.md`,
> `facade-services.md`, `risques-et-effort.md`, ce document.

## Matrice de couverture

| Exigence (spec) | Scénario | Couvert par |
|---|---|---|
| **Cartographie de la surface UI existante** | Inventaire des écrans | `cartographie.md` §2 (14 vues, composants par écran) |
| | Recensement des points de contact moteur | `cartographie.md` §2 (appels `repo`/`generator`/`templates`/`printing`/`mailer`/`doc_filler`) + §4 (sync vs long) |
| **Comparaison argumentée Flutter vs React** | Grille de critères pondérés | `design.md` **D2** (grille 7 critères, poids = 100, notes 0–5) |
| | Conclusion traçable | `design.md` D2 (score 352 vs 433 ; facteurs décisifs = écosystème + vitesse/coût) |
| **Contrat d'architecture cible frontend/backend** | Réutilisation du moteur sans modification | `design.md` **D1** + `facade-services.md` §1/§2 (façade fine, moteur inchangé) |
| | Choix de canal IPC arbitré | `design.md` **D3** (HTTP localhost vs WebSocket vs JSON-RPC stdio → HTTP recommandé) |
| | Opérations longues et erreurs | `facade-services.md` §4 (progression SSE/jobs) + §5 (codes d'erreur) ; `design.md` D3 |
| **Préservation des invariants existants** | Contrainte Windows / Word COM conservée | `facade-services.md` §6 (ligne Word COM) ; `design.md` D1 |
| | Préservation des données et idempotence | `facade-services.md` §6 (données, idempotence, migrations, backup, secrets) ; `cartographie.md` §5 |
| **Évaluation des risques et de l'effort** | Registre des risques | `risques-et-effort.md` §1 (R1–R12, prob × impact × atténuation) |
| | Estimation d'effort exploitable | `risques-et-effort.md` §2 (lots L0–L5, fourchettes comparables) |
| **Plan de migration incrémental** | Découpage par écran et premier écran pilote | `design.md` **D4** (pilote = Paramétrage, puis Patients) + `risques-et-effort.md` §2 (séquence L2→L5) |
| **Recommandation finale motivée** | Décision go / no-go traçable | `design.md` **D2** (recommandation : migrer vers React, coquille Tauri) + *Migration Plan* / *Open Questions* |

## Couverture des décisions complémentaires (design.md)

| Décision | Sujet | Statut |
|---|---|---|
| D5 | Packaging Windows (Tauri `externalBin` + sidecar PyInstaller) | tranché |
| D6 | Stack frontend (React 19 + Vite + Tailwind v4 + shadcn + TanStack) | tranché |
| D7 | Backend FastAPI + client TS généré | tranché |
| — | Mode web (Flet web) | **reporté, porte ouverte** (tâche 5.4) |

## Verdict de complétude

**Toutes les exigences du spec sont couvertes** ; aucun scénario n'est orphelin. Points laissés
**ouverts et explicitement non bloquants** (à acter en revue, tâche 6.2) :

1. **Organisation du repo** (`ui/` pour React/Tauri, `crm/server.py` pour FastAPL) — défaut
   proposé, à confirmer à l'implémentation (`design.md` *Open Questions*).
2. **Seuil de latence ressentie** des écrans listes — à fixer comme critère de recette
   (`risques-et-effort.md` R3 ; tâche 3.3).
3. **Mode web** — reporté (`design.md` D2/Open Questions).

> Reste la **tâche 6.2** : relecture de l'étude avec le demandeur et **décision actée**
> (go/no-go). Elle requiert une validation humaine et n'est pas cochée automatiquement.
