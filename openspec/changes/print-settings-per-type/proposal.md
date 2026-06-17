## Why

Aujourd'hui, le bouton « Imprimer » envoie le document à l'imprimante configurée
en utilisant les réglages **par défaut de l'imprimante** : aucun contrôle du format
papier ni de la couleur. Or le cabinet imprime ses documents sur des formats
différents selon leur nature — **demandes de radio et examens biologiques sur A5**,
**factures / notes d'honoraires sur A4** — et doit aujourd'hui reconfigurer l'imprimante
à la main entre deux impressions, ou récupérer des sorties au mauvais format.

## What Changes

- **Réglages d'impression par type de document.** Chaque type (= nom du modèle :
  `demande_radio`, `examen_biologique`, `facture`, `note_honoraires`…) peut se voir
  attribuer un **format papier** (A4, A5) et un **mode couleur** (couleur / noir & blanc)
  par défaut, configurés une fois dans **Paramétrage › Imprimante**.
- **Application silencieuse au moment d'imprimer.** Le bouton « Imprimer » d'un document
  applique automatiquement le format et la couleur mémorisés pour son type, sans aucune
  boîte de dialogue (même ergonomie que le choix d'imprimante actuel). Une facture part
  en A4, une demande de radio en A5, sans intervention.
- **Repli sûr.** Un type sans réglage explicite imprime avec les réglages par défaut de
  l'imprimante (comportement actuel) ; rien n'est imposé tant que l'utilisateur n'a pas
  choisi.
- **Moteur d'impression étendu.** `crm/printing.py` applique le format papier et la
  couleur au pilote d'impression (via le DEVMODE de l'imprimante) avant de rendre les
  pages, au lieu d'utiliser systématiquement le DEVMODE par défaut.
- **Stockage sans migration de schéma.** Les réglages sont mémorisés dans la table `meta`
  via `repo.get_setting`/`set_setting` (comme `printer_name` aujourd'hui) — aucune
  modification du schéma SQLite, donc aucun risque pour les données de production.

## Capabilities

### New Capabilities
- `print-settings`: réglages d'impression (format papier, couleur/N&B) définis par type
  de document, mémorisés et appliqués automatiquement et silencieusement à l'impression,
  avec repli sur les réglages par défaut de l'imprimante.

### Modified Capabilities
<!-- Aucune capability existante : openspec/specs/ est vide. -->

## Impact

- **Code** :
  - `crm/printing.py` — application du format papier (`dmPaperSize`) et de la couleur
    (`dmColor`) au DEVMODE de l'imprimante avant le rendu GDI (`ResetDC`) ; nouveaux
    paramètres `paper`/`color` sur `print_file`. Zone délicate à vérifier sur sortie
    réelle (cf. CLAUDE.md : pilotage GDI/COM non testable en CI).
  - `crm/repo.py` (ou helper dédié) — lecture/écriture des réglages par type dans `meta`
    (clé unique JSON ou clés préfixées), liste des types connus depuis les modèles.
  - `crm/app.py` — section **Paramétrage › Imprimante** enrichie : un tableau « type de
    document → format / couleur » ; `_print_file` résout le type du document et passe les
    réglages mémorisés à `printing.print_file`.
- **Données** : aucune migration de schéma. Réglages stockés dans `meta` (additif,
  réversible, conforme aux règles de préservation des données de CLAUDE.md).
- **Plateforme** : Windows uniquement (déjà le cas). Le contrôle du format/couleur dépend
  des capacités du pilote d'imprimante ; les formats non supportés par l'imprimante
  retombent sur son défaut.
- **Modèles** : aucun `.docx` à modifier ; les réglages sont portés par l'application.
