## Context

Actuellement, l'application permet de générer des documents à partir de fichiers modèles `.docx` stockés dans le dossier `templates/` de l'application. Chaque modèle est associé à une catégorie facultative via la table SQLite `template_meta`. Les catégories elles-mêmes sont stockées dans la table `categories`.

L'action « Ouvrir dans WhatsApp (wa.me) » génère un message pré-rempli figé dans le code React du frontend :
`Bonjour ${patient.prenom || ''} ${patient.nom || ''}, voici votre ${humanize(d.type).toLowerCase()}.`

Pour simplifier la gestion, l'utilisateur souhaite configurer un message WhatsApp pré-rempli **par catégorie** de documents plutôt que par modèle individuel. Il souhaite également pouvoir importer/exporter en masse cette configuration de catégories (comprenant les messages WhatsApp) via un fichier Excel `.xlsx`.

## Goals / Non-Goals

**Goals:**
- Configurer un message WhatsApp personnalisé au niveau de chaque **catégorie** de documents.
- Supporter le remplacement dynamique de variables (ex. `<PRENOM>`, `<NOM>`, `<DOCUMENT>`) lors de la construction du lien `wa.me` ou de l'envoi WhatsApp API.
- Fournir des fonctionnalités d'import et d'export en masse de ces catégories (avec couleurs, icônes et messages WhatsApp associés) via un fichier Excel `.xlsx`.
- Assurer le repli sur le message standard configuré dans `config.ini` si aucun message personnalisé n'est défini pour la catégorie du document (ou si le document n'a pas de catégorie).

**Non-Goals:**
- Configurer des messages WhatsApp spécifiques par modèle individuel (la configuration se fait uniquement au niveau de la catégorie).

## Decisions

### D1 — Évolution du schéma de base de données (SQLite)
Nous incrémentons `SCHEMA_VERSION` à `15` dans `apps/api/crm/db.py`.
Nous ajoutons une migration pour la table `categories` afin de lui ajouter la colonne `whatsapp_message` TEXT :
```python
if not _column_exists(conn, "categories", "whatsapp_message"):
    conn.execute("ALTER TABLE categories ADD COLUMN whatsapp_message TEXT")
```
Nous veillerons à ce que l'initialisation de la table contienne également cette colonne.

### D2 — Évolution du Repository Backend (`repo.py`)
Mise à jour de la dataclass `Category` et des fonctions associées :
- `Category` inclut désormais le champ optionnel `whatsapp_message: Optional[str] = None`.
- Mise à jour de `upsert_category`, `list_categories`, `get_category` et `rename_category` pour lire, écrire et propager le champ `whatsapp_message`.

### D3 — API REST (`server.py`)
1. **Pydantic Models** :
   - Mise à jour de `CategoryOut` et `CategoryUpsertIn` pour inclure le champ optionnel `whatsapp_message: Optional[str] = None`.
2. **Endpoints d'Import/Export (.xlsx)** :
   - Ajout de `GET /api/categories/export` qui génère un fichier Excel `.xlsx` contenant toutes les catégories (Colonnes : `Nom`, `Couleur`, `Icone`, `Ordre`, `Message WhatsApp`).
   - Ajout de `POST /api/categories/import` qui traite le fichier Excel téléversé pour mettre à jour ou créer les catégories.

### D4 — Résolution du message WhatsApp dans le Frontend (React)
Dans `DocumentsTab.tsx` :
- Nous récupérons la catégorie du document (dérivée de la catégorie de son modèle).
- Si le document possède une catégorie et que cette catégorie dispose d'un message WhatsApp personnalisé, nous l'utilisons. Sinon, nous utilisons la configuration globale de repli.
- Nous implémentons une fonction de formatage `formatDynamicMessage(templateText: string, patient: Patient, docType: string)` qui remplace :
  - `<PRENOM>` -> `patient.prenom`
  - `<NOM>` -> `patient.nom`
  - `<DOCUMENT>` -> `humanize(docType).toLowerCase()`
- Nous encodons ce texte et l'injectons dans le lien `wa.me`.

### D5 — Interface utilisateur Paramétrage -> Modèles
- Dans `ModelesTab.tsx`, à côté de chaque titre de catégorie (ex. "Facturation"), ajout d'un bouton d'édition (icône Settings/Pencil) qui ouvre un dialogue ou une feuille (`Sheet`) permettant d'éditer les propriétés de la catégorie (Couleur, et son Message WhatsApp associé).
- Ajout de boutons d'import/export de masse pour les catégories en haut de l'onglet Modèles.

### D6 — Message de repli configurable dans `config.ini`
- Nous ajoutons une section `[whatsapp]` dans `apps/api/config.ini` avec le paramètre `message_repli`.
- Nous modifions le chargement de la configuration dans `apps/api/src/config.py` pour lire ce paramètre (valeur par défaut : `Bonjour <PRENOM> <NOM>, voici votre <DOCUMENT>.`).
- L'endpoint `GET /api/settings/whatsapp` dans `server.py` renvoie cette valeur de repli dans le champ `fallback_message` du modèle `WhatsAppSettingsOut`, de sorte que le frontend y accède directement.

## Risks / Trade-offs

- **Risk: Catégorie orpheline ou inexistante**
  - *Mitigation:* Si un document n'a pas de catégorie, ou si sa catégorie a un message WhatsApp vide, le système applique proprement le message de repli global.
