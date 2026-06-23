## 1. Logique FDI pure (`crm/repo.py`)

- [x] 1.1 Ajouter les ensembles de dents FDI : `DENTS_PERMANENTES` (11–18, 21–28, 31–38, 41–48) et `DENTS_TEMPORAIRES` (51–55, 61–65, 71–75, 81–85), structurés par quadrant pour permettre la disposition en croix
- [x] 1.2 Ajouter `is_fdi_valide(num: str) -> bool` et `fdi_quadrant(num: str) -> int | None` (helpers purs, sans Flet, testables)
- [x] 1.3 Ajouter `denture_par_defaut(date_naissance: str | None) -> "adulte" | "enfant"` (défaut enfant pour un jeune âge, adulte sinon ou si naissance inconnue)
- [x] 1.4 Vérifier que `normalize_dents` reste **inchangé** (format de persistance « 26, 27 » et tolérance saisie libre conservés)

## 2. Composant odontogramme natif Flet (`crm/app.py`)

- [x] 2.1 Créer une fabrique `_odontogramme(...)` renvoyant un handle (`SimpleNamespace`) : `.control`, `.refresh()`, `.set_denture()` ; la sélection reste portée par le parent via les callbacks `is_selected`/`on_toggle` (source de vérité unique)
- [x] 2.2 Rendre les 4 quadrants en croix (maxillaire haut / mandibulaire bas ; droite patient à gauche de l'écran) avec une case-dent compacte cliquable **affichant toujours son numéro FDI**
- [x] 2.3 Gérer l'état sélectionné par dent (fond plein `NAVY` + numéro blanc ; numéro **toujours visible**) et le **toggle** au clic
- [x] 2.4 Ajouter la bascule denture **adulte / enfant** (boutons Adulte/Enfant) qui change l'ensemble de dents affiché sans perdre la sélection courante
- [x] 2.5 Initialiser la denture par défaut via `repo.denture_par_defaut(patient.date_naissance)` quand l'âge est connu
- [x] 2.6 Garder le composant **compact** (bouton-dent 30×30, quadrants serrés, encart à bordure légère)

## 3. Saisie en bloc (validée par Entrée) dans `_acte_card` (`crm/app.py`)

- [x] 3.1 Ajout en bloc à la validation (`on_submit`/Entrée) : découper tout le champ sur `,` `;` espace / saut de ligne, ajouter tous les numéros d'un coup, vider le champ ; **pas** de commit au fil de la frappe (aucun `on_change`)
- [x] 3.2 Déclencher aussi l'ajout par le bouton « + » et par `on_blur` (filet de sécurité)
- [x] 3.3 Dédupliquer à l'ajout (pas de doublon dans `dents_list`)
- [ ] 3.4 Vérifier la dictée vocale : dicter plusieurs dents enchaînées (« 26 27 28 ») puis Entrée les ajoute toutes (test manuel au fauteuil) — *implémentation prête ; confirmation réelle = gate manuel*

## 4. Source de vérité + intégration (`crm/app.py`)

- [x] 4.1 Faire de `dents_list` la **source de vérité unique** ; `sync()` re-rend **l'odontogramme** (plus de chips dans le formulaire — `chips_row`/`render_chips`/`remove_dent` supprimés)
- [x] 4.2 Câbler : champ → ajout en bloc → `sync()` ; **clic/re-clic sur le schéma** → toggle → `sync()` (le retrait se fait sur l'odontogramme, plus de croix de chip)
- [x] 4.3 Refléter le surlignage des dents FDI valides sur le schéma à partir de `dents_list` ; ne **rien** surligner pour un jeton non FDI (`repo.is_fdi_valide`)
- [x] 4.4 Insérer l'odontogramme **sous** la `Row` champ + « + » dans la `Column` de `_acte_card` ; `read()` inchangé et handle public préservé (param `date_naissance` ajouté en kwarg optionnel rétro-compatible)

## 5. Vérification (manuelle — pas de CI, voir CLAUDE.md)

- [ ] 5.1 Desktop (`python crm_app.py`) : ajouter un acte, saisir plusieurs dents puis Entrée (et tester « + » / perte de focus), cliquer des dents, **retirer par re-clic sur le schéma** — état cohérent ; vérifier qu'**aucun chip** n'apparaît dans le formulaire et que **chaque dent affiche son numéro**
- [ ] 5.2 Web (`python crm_web.py`) : revérifier clics, focus et rendu identiques au desktop
- [ ] 5.3 Bascule adulte/enfant et défaut par âge sur un patient avec et sans date de naissance — *logique `denture_par_defaut` testée ; bascule UI = gate manuel*
- [ ] 5.4 Enregistrer l'acte et vérifier la persistance « 26, 27 » dans `prestations.dents` (format inchangé) ; rouvrir l'acte et confirmer la pré-sélection des chips et du schéma — *`read()` inchangé (logique testée) ; aller-retour UI = gate manuel*
- [ ] 5.5 Saisie d'un jeton non FDI « 19 » : chip créé et persisté, aucune dent surlignée, acte valide — *logique testée ; rendu UI = gate manuel*
- [x] 5.6 Confirmer l'absence de bump `SCHEMA_VERSION` et de migration (changement purement additif/UI) — vérifié : `git diff` ne touche que `crm/app.py` et `crm/repo.py`, `crm/db.py` intact
