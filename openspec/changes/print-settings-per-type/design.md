## Context

`crm/printing.py` imprime aujourd'hui en pilotant l'imprimante via GDI (`win32ui` +
`ImageWin.Dib`). La chaîne est : PDF/JPG → images RGB (`fitz`/Pillow) → `CreatePrinterDC`
→ `StartDoc/StartPage/EndPage`. Le DC est créé avec `hdc.CreatePrinterDC(printer_name)`,
qui hérite du **DEVMODE par défaut** de l'imprimante : ni le format papier ni la couleur
ne sont contrôlés par l'application.

Le « type » d'un document est déjà connu : `Document.type` vaut le nom du modèle ayant
servi à le générer (`facture`, `demande_radio`, `examen_biologique`…). C'est la clé
naturelle pour des réglages par type. L'imprimante cible est déjà mémorisée dans `meta`
(`printer_name`) sans migration de schéma — ce change suit exactement le même modèle.

Le cabinet veut, sans clic supplémentaire au quotidien : factures/notes en A4, demandes
de radio et examens biologiques en A5, avec un choix couleur/N&B par type. Décision
produit déjà tranchée : **réglages mémorisés par type, appliqués silencieusement**.

## Goals / Non-Goals

**Goals:**

- Mémoriser un couple (format papier, mode couleur) par type de document.
- Appliquer ces réglages automatiquement et silencieusement au clic « Imprimer ».
- Repli sûr et identique au comportement actuel quand un type n'a pas de réglage.
- Zéro migration de schéma SQLite ; persistance via `meta`.
- Configuration centralisée dans Paramétrage › Imprimante.

**Non-Goals:**

- Pas de boîte de dialogue de réglages au moment d'imprimer (choix produit retenu).
- Pas de réglages par document individuel (granularité = type).
- Pas de contrôle d'autres paramètres (recto-verso, bac, copies, orientation, échelle).
- Pas de dépendance à la fonctionnalité « catégories » (`organize-documents-by-category`),
  encore au stade proposal — la clé reste le **type** (nom du modèle), pas la catégorie.
- Pas de support multi-plateforme (Windows + GDI uniquement, comme l'existant).

## Decisions

### Décision 1 — Clé de réglage = type de document (nom du modèle)

On indexe les réglages par `Document.type`. Avantages : déjà présent sur chaque document
et chaque modèle, stable, aligné sur le mot employé par l'utilisateur. Alternative
écartée : indexer par « catégorie » — la capacité catégories n'est pas encore implémentée
et ajouterait un couplage à un change non appliqué. Si les catégories arrivent plus tard,
les réglages pourront être ré-indexés sans casser ce design (les deux sont des chaînes).

### Décision 2 — Stockage dans `meta`, en JSON, sans migration

Un seul enregistrement `meta` sous une clé dédiée (ex. `print_settings`) contenant un JSON
`{ "<type>": { "paper": "A4"|"A5", "color": "color"|"mono" }, ... }`, lu/écrit via
`repo.get_setting`/`set_setting`. Avantages : additif, réversible, aucune `ALTER`/bump de
`SCHEMA_VERSION`, conforme aux règles de préservation des données de CLAUDE.md (exactement
le modèle de `printer_name`). Alternative écartée : clés `meta` préfixées par type
(`print_paper:<type>`) — plus de lignes à gérer, énumération moins directe. Un petit
module/helper (`crm/print_settings.py` ou fonctions dans `repo.py`) encapsule la
sérialisation et expose `get_settings_for(type)` / `set_settings_for(type, paper, color)`
/ `all_settings()`.

### Décision 3 — Application via DEVMODE + `ResetDC` dans `crm/printing.py`

Avant le rendu, on récupère le DEVMODE de l'imprimante
(`win32print.OpenPrinter` → `GetPrinter(h, 2)["pDevMode"]`), on positionne :
- `pDevMode.PaperSize` ← `DMPAPER_A4` (9) ou `DMPAPER_A5` (11) et le bit
  `DM_PAPERSIZE` dans `pDevMode.Fields` ;
- `pDevMode.Color` ← `DMCOLOR_COLOR` (2) ou `DMCOLOR_MONOCHROME` (1) et le bit `DM_COLOR`.

Puis on crée le DC et on applique le DEVMODE modifié via `hdc.ResetDC(pDevMode)` (PyCDC)
avant `StartDoc`. Le calcul d'échelle reste basé sur `GetDeviceCaps` après `ResetDC`, donc
le passage A4→A5 réajuste automatiquement la mise à l'échelle « centrée, ratio préservé »
existante. La signature devient
`print_file(path, printer_name, *, paper=None, color=None, doc_name=None)` ; `paper`/`color`
à `None` ⇒ on ne touche pas au DEVMODE (repli = comportement actuel). Constantes de format
définies en clair dans `printing.py` (pas de dépendance à `win32con` pour les valeurs DM,
qui sont stables).

### Décision 4 — UI : tableau « type → format / couleur » dans Paramétrage › Imprimante

La carte imprimante existante gagne une section listant les **types connus** (union des
noms de modèles via `templates.list_templates()` et des `type` déjà présents dans
`documents`), chacun avec deux `Dropdown` : Format (A4 / A5 / « Défaut imprimante ») et
Couleur (Couleur / Noir & blanc / « Défaut imprimante »). Un seul bouton « Enregistrer »
persiste l'ensemble. `_print_file` lit `Document.type`, résout les réglages et les passe à
`printing.print_file`. Le reste de la logique de `_print_file` (imprimante manquante,
indisponible, exécution en tâche de fond) est inchangé.

## Risks / Trade-offs

- **[Le pilote ignore/rejette un format ou une couleur]** → Mitigation : `ResetDC` est
  best-effort ; on enveloppe la modification du DEVMODE de sorte qu'un échec retombe sur le
  DEVMODE par défaut sans faire échouer l'impression (cf. exigence « Tolérance aux
  capacités du pilote »). L'aperçu n'est pas garanti conforme si l'imprimante n'offre pas
  le format.
- **[Manipulation du DEVMODE pywin32 fragile / objet non modifiable selon le pilote]** →
  Mitigation : tester sur l'imprimante réseau réelle du cabinet (zone non testable en CI,
  comme Word COM, cf. CLAUDE.md) ; prévoir un repli si `pDevMode` est `None`.
- **[Mauvais réglage appliqué silencieusement (mauvais format) non détecté par
  l'utilisateur]** → Mitigation : la page de test et l'affichage clair du réglage par type
  dans Paramétrage ; le repli « Défaut imprimante » reste sélectionnable pour annuler.
- **[Type de document non reconnu / renommage de modèle]** → Mitigation : un type sans
  entrée retombe sur le défaut imprimante ; les réglages orphelins (modèle renommé) sont
  inertes et n'affectent rien.
- **[Couplage futur avec les catégories]** → Trade-off accepté : on reste sur le type ;
  ré-indexation possible plus tard sans changement structurel.

## Migration Plan

Aucune migration de schéma. Déploiement = remplacement de l'`.exe`. À la première
ouverture post-mise à jour, la clé `meta.print_settings` est absente ⇒ tous les types
impriment comme avant (repli). L'utilisateur définit ses réglages dans Paramétrage. Retour
arrière : supprimer la clé `meta.print_settings` (ou revenir à l'`.exe` précédent) rétablit
le comportement par défaut ; les données patients/documents ne sont jamais touchées.

## Open Questions

- Faut-il proposer d'autres formats que A4/A5 (A3, Letter) dès cette version ? Par défaut :
  A4 + A5 seulement, suffisants pour le besoin exprimé ; l'ensemble est extensible.
- Faut-il une valeur par défaut « intelligente » pré-remplie (A5 pour les types contenant
  « radio »/« bio », A4 sinon) ? Par défaut : non — laisser l'utilisateur choisir
  explicitement, repli neutre tant que rien n'est réglé.
