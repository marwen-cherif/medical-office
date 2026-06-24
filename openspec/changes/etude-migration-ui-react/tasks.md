> Périmètre : **étude de faisabilité seule** — ces tâches produisent et valident des
> livrables documentaires (analyse, grille, plan, recommandation). **Aucun code applicatif**
> n'est écrit. Le livrable consolidé est rédigé sous
> `openspec/changes/etude-migration-ui-react/`.

## 1. Cartographie de l'existant

- [ ] 1.1 Inventorier tous les écrans de `crm/app.py` (Tableau de bord, Patients + fiche à
      onglets, Finances, Paramétrage, Travaux) avec, pour chacun, les composants UI utilisés
- [ ] 1.2 Recenser les points de contact UI → moteur (appels vers `crm/repo.py`,
      `crm/generator.py`, `crm/templates.py`, `crm/printing.py`, `src/mailer.py`,
      `src/doc_filler.py`)
- [ ] 1.3 Marquer les opérations longues (génération Word COM, envoi/polling Mailjet,
      impression GDI) et les flux de dialogues/calendriers réutilisables
- [ ] 1.4 Figer cette cartographie comme **référentiel de complétude** (toute cible devra la
      couvrir à 100 %)

## 2. Contrat d'architecture cible et interface IPC

- [ ] 2.1 Décrire la façade de services backend (une opération par cas d'usage UI) réutilisant
      le moteur Python **sans le modifier**
- [ ] 2.2 Spécifier le contrat IPC : formats d'échange, codes d'erreur, et remontée de
      progression pour les opérations longues
- [ ] 2.3 Comparer les canaux IPC (HTTP localhost / WebSocket / JSON-RPC stdio) et acter le
      choix recommandé avec sa justification
- [ ] 2.4 Démontrer la préservation des invariants : Word COM/Windows, propriété des données
      par le backend (`data/`, `output/`, `templates/`, `config.ini`), idempotence par nom de
      fichier, migrations `SCHEMA_VERSION`/`_migrate()` inchangées
- [ ] 2.5 Décrire le packaging Windows (frontend natif + backend Python PyInstaller en
      sidecar, découverte du port, cycle de vie du process, survie des données entre mises à jour)

## 3. Comparaison Flutter vs React

- [ ] 3.1 Confirmer les critères et **calibrer les pondérations** avec le cabinet (qualité
      d'UI vs coût/écosystème) — figer la grille définitive
- [ ] 3.2 Justifier chaque note par option (Flutter/Dart vs React/Tauri, Electron en repli)
      par des éléments factuels, pas des préférences
- [ ] 3.3 Valider les hypothèses sensibles (latence IPC ressentie sur écrans listes, taille du
      livrable, impression GDI pilotée via le sidecar) — par analyse, mesure ou retours d'usage
- [ ] 3.4 Calculer le **score agrégé final** par option et expliciter les facteurs décisifs et
      l'écart entre options

## 4. Risques et effort

- [ ] 4.1 Établir le registre des risques (probabilité, impact, atténuation), incluant le
      couplage Word COM / IPC / packaging Windows
- [ ] 4.2 Estimer l'effort par lot (mise en place IPC, socle frontend, portage par écran,
      packaging, recette) sous une forme comparable

## 5. Plan de migration et recommandation

- [ ] 5.1 Ordonner les écrans à migrer, désigner l'écran pilote justifié et décrire la
      cohabitation Flet ↔ nouvelle UI pendant la transition
- [ ] 5.2 Définir la stratégie de repli (rollback : rester sur Flet sans perte tant que la
      cohabitation dure)
- [ ] 5.3 Rédiger la **recommandation finale** : go/no-go, techno retenue le cas échéant,
      conditions, en la reliant aux objectifs (indépendance Flet, maintenabilité, qualité UI)
      et au score de la grille
- [x] 5.4 Trancher la question du **mode web** (Flet web) → **reporter (porte ouverte)** :
      cible immédiate desktop Tauri, web ré-accessible plus tard via FastAPI + React

## 6. Revue et validation du livrable

- [ ] 6.1 Vérifier que chaque exigence du spec `migration-ui-react` est couverte par le
      livrable (traçabilité exigence → section)
- [ ] 6.2 Relire l'étude avec le demandeur et acter la décision (ou la liste des éléments
      manquants à compléter)
