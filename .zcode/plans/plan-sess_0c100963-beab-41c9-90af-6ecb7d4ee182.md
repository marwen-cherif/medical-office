Je vais rédiger les artefacts OpenSpec complets pour ce changement, en respectant les conventions exactes du repo (FR + mots-clés EN, structure proposal/design/tasks/specs).

**Slug du changement :** `installation-worker-de-fond`
**Capabilities touchées :**
- `service-de-fond-windows` (NOUVELLE — couvre le worker tray `crm-tray.exe` + autostart HKCU Run déjà implémentés)
- `installation-mise-a-jour` (NOUVELLE — couvre l'installer NSIS custom à venir : détection registre, préservation config.ini, migration par script)

**Fichiers à créer dans `openspec/changes/installation-worker-de-fond/` :**
- `.openspec.yaml` (metadata)
- `proposal.md` (Why / What Changes / Capabilities / Impact)
- `design.md` (Context / Goals-NonGoals / Decisions D1-D5 / Risques / Migration Plan / Open Questions)
- `tasks.md` (sections numérotées avec checkboxes ; worker tray = `[x]` déjà fait, installer = `[ ]` à faire)
- `specs/service-de-fond-windows/spec.md` (delta ADDED)
- `specs/installation-mise-a-jour/spec.md` (delta ADDED)

Aucune spec existante n'est MODIFIED/REMOVED (les deux capabilities sont nouvelles). Le contenu sera en français avec SHALL/WHEN/THEN en anglais, conformément à `openspec/config.yaml`.

À l'archivage (via `/opsx:archive`), le dossier passera dans `changes/archive/2026-07-18-installation-worker-de-fond/` et les deltas se synchroniseront dans `openspec/specs/`.

Je ne crée pas encore les specs canoniaques dans `openspec/specs/` (c'est le rôle de l'étape `/opsx:sync` post-implémentation, conformément au workflow).