# Recette du pilote Paramétrage (Windows + Word — manuelle)

> Cette recette **ne peut pas être automatisée** : génération/impression exigent
> **Windows + Word + une imprimante**, et la parité se juge par comparaison
> visuelle avec l'oracle **Flet**. Elle se déroule sur un poste outillé (Rust +
> MSVC Build Tools pour produire l'exe Tauri), sur une **vraie base** copiée de
> `backups/`.

## Pré-requis

1. Poste Windows 11 avec **Word installé** et au moins **une imprimante**.
2. Toolchain de build : Python (+ `requirements.txt`), Node/npm, **Rust (rustup)**,
   **VS Build Tools** (MSVC + Windows SDK), WebView2.
3. Construire l'exe : `.\build-crm-react.bat` → installeur NSIS.
4. Copier une **vraie `cabinet.db`** depuis `backups/` dans `data/` à côté de l'exe.

## 6.1 — Recette de parité contre Flet

Référentiel : `cartographie.md` de l'étude archivée
(`openspec/changes/archive/2026-06-24-etude-migration-ui-react/`). Lancer **Flet**
(`python crm_app.py`) et **React** (l'exe Tauri) côte à côte sur la **même base**.

| Domaine | Opération | Flet (oracle) | React | Verdict |
|---|---|---|---|---|
| Modèles | Lister (groupés par catégorie) | | | |
| Modèles | Créer un modèle | | | |
| Modèles | Renommer (catégorie reportée) | | | |
| Modèles | Supprimer | | | |
| Modèles | Configurer les variables | | | |
| Modèles | Ouvrir dans Word | | | |
| Modèles | Assigner une catégorie | | | |
| Email | Lister / créer / modifier / supprimer | | | |
| Email | Définir par défaut | | | |
| Imprimante | Choisir + enregistrer | | | |
| Imprimante | Format/couleur par type | | | |
| Imprimante | **Test d'impression** (page sort) | | | |
| Actes | Lister (recherche + inactifs) | | | |
| Actes | Créer / modifier | | | |
| Actes | Activer / désactiver | | | |

**Cohabitation sans divergence** : créer un acte dans React → il apparaît dans Flet
après rafraîchissement (et inversement). Idem catégorie de modèle, imprimante.

## 6.2 — Latence ressentie des listes

Protocole : sur la vraie base, mesurer le temps **clic → liste affichée** pour
Modèles, Actes (recherche), Email, Imprimante. Comparer à Flet.

| Liste | Flet | React (1er) | React (cache) | Seuil |
|---|---|---|---|---|
| Modèles | | | | < 300 ms |
| Actes (recherche) | | | | < 300 ms |
| Email | | | | < 300 ms |

**Seuil de recette proposé** (à acter, cf. étude R3) : **≤ 300 ms** en perception
sur une liste déjà visitée (cache TanStack Query chaud), **≤ 800 ms** au premier
affichage. Au-delà, investiguer (pagination, indices, taille de réponse).

## 6.3 — Go / No-Go intermédiaire

Critères de **GO** vers le portage des écrans denses (Patients, Tableau de bord,
Finances, Travaux, Prestataires) :

- [ ] Parité fonctionnelle de Paramétrage (§6.1) — aucun écart bloquant.
- [ ] Cohabitation sans divergence de données démontrée.
- [ ] Latence sous le seuil acté (§6.2).
- [ ] Chaîne 2 process stable : démarrage/arrêt du sidecar propres, pas de
      process orphelin, handshake fiable au lancement.
- [ ] Test d'impression OK (202 + progression SSE + page sortie).
- [ ] Invariants confirmés (backup/migrations/anti-downgrade/Word COM/secrets) —
      déjà vérifiés en automatique (cf. §5 des tâches).

**Décision** : ______ (GO / NO-GO)  —  **Date** : ______  —  **Par** : ______

> Note : tout le reste de la migration (lots 5.x et 6.x hors recette manuelle) est
> implémenté et vérifié automatiquement. Ce document est le **seul reste** : une
> passe manuelle sur poste Windows+Word avec l'exe packagé.
