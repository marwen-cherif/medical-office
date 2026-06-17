## 1. Persistance des réglages (meta, sans migration)

- [ ] 1.1 Définir la structure JSON des réglages `{ "<type>": { "paper": "A4"|"A5"|null, "color": "color"|"mono"|null } }` et la clé `meta` dédiée (ex. `PRINT_SETTINGS_KEY = "print_settings"`).
- [ ] 1.2 Ajouter les helpers de lecture/écriture (dans `crm/repo.py` ou un module `crm/print_settings.py`) : `get_settings_for(conn, type)`, `set_settings_for(conn, type, paper, color)`, `all_settings(conn)` — sérialisation/désérialisation JSON via `repo.get_setting`/`set_setting`, sans modifier le schéma ni `SCHEMA_VERSION`.
- [ ] 1.3 Gérer la robustesse : clé absente ou JSON invalide ⇒ dictionnaire vide (repli sûr), valeurs inconnues ignorées.

## 2. Moteur d'impression (crm/printing.py)

- [ ] 2.1 Ajouter les constantes de format/couleur (`DMPAPER_A4 = 9`, `DMPAPER_A5 = 11`, `DMCOLOR_COLOR = 2`, `DMCOLOR_MONOCHROME = 1`, bits `DM_PAPERSIZE`/`DM_COLOR`) et une table format → valeur DM.
- [ ] 2.2 Implémenter la récupération + modification du DEVMODE de l'imprimante (`win32print.OpenPrinter` → `GetPrinter(h, 2)["pDevMode"]`), en positionnant `PaperSize`/`Color` et les bits `Fields` correspondants uniquement pour les paramètres fournis.
- [ ] 2.3 Étendre `print_file(path, printer_name, *, paper=None, color=None, doc_name=None)` et `_print_images(...)` pour appliquer le DEVMODE modifié via `hdc.ResetDC(devmode)` avant `StartDoc` ; recalculer l'échelle sur `GetDeviceCaps` après `ResetDC`.
- [ ] 2.4 Repli sûr : `paper`/`color` à `None` ⇒ ne pas toucher au DEVMODE ; `pDevMode` `None` ou échec de modification ⇒ impression avec le DEVMODE par défaut, sans lever d'exception (cf. exigence « Tolérance aux capacités du pilote »).

## 3. Intégration UI — impression (crm/app.py)

- [ ] 3.1 Dans `_print_file`, résoudre `Document.type`, lire les réglages mémorisés et les passer à `printing.print_file(path, printer, paper=..., color=...)` — aucune boîte de dialogue (application silencieuse).
- [ ] 3.2 Compléter le message d'audit `document_imprime` pour tracer le format/couleur appliqués (ex. `#id type -> imprimante (A5, N&B)`).

## 4. Intégration UI — Paramétrage › Imprimante (crm/app.py)

- [ ] 4.1 Construire la liste des **types connus** : union de `templates.list_templates()` (noms de modèles) et des `type` distincts présents dans `documents`.
- [ ] 4.2 Ajouter à la carte imprimante un tableau « type → Format / Couleur » : deux `Dropdown` par type (Format : A4 / A5 / « Défaut imprimante » ; Couleur : Couleur / Noir & blanc / « Défaut imprimante »), pré-remplis depuis les réglages enregistrés.
- [ ] 4.3 Bouton « Enregistrer » persistant l'ensemble des réglages par type (`set_settings_for` pour chaque type), avec message de confirmation et entrée d'audit.
- [ ] 4.4 Afficher « Par défaut de l'imprimante » pour un type non configuré ; conserver l'ergonomie clavier existante (Ctrl+S enregistrer).

## 5. Vérification (manuelle, Windows + imprimante réelle)

- [ ] 5.1 Régler « facture » sur A4 et « demande_radio »/« examen_biologique » sur A5, imprimer un document de chaque type et vérifier le format de sortie réel.
- [ ] 5.2 Vérifier le mode couleur (Couleur vs Noir & blanc) sur une imprimante couleur.
- [ ] 5.3 Vérifier le repli : type sans réglage ⇒ impression au format/couleur par défaut de l'imprimante (comportement antérieur).
- [ ] 5.4 Vérifier un format non pris en charge par l'imprimante : l'impression aboutit quand même sans exception.
- [ ] 5.5 Vérifier la persistance après redémarrage de l'application et sur une copie d'une base `cabinet.db` de production (chargement intact des patients/documents).
