## 1. Base de données et Repository

- [x] 1.1 Incrémenter `SCHEMA_VERSION` à 16 dans [db.py](file:///apps/api/crm/db.py).
- [x] 1.2 Ajouter la migration dans la fonction `_migrate` de [db.py](file:///apps/api/crm/db.py) pour ajouter la colonne `whatsapp_message` TEXT à la table `categories`.
- [x] 1.3 Mettre à jour la requête de création de `categories` dans `_SCHEMA` de [db.py](file:///apps/api/crm/db.py) pour inclure la colonne `whatsapp_message` TEXT.
- [x] 1.4 Mettre à jour la structure et les fonctions liées à `Category` (notamment `upsert_category`, `list_categories`, `get_category`, `rename_category`) dans [repo.py](file:///apps/api/crm/repo.py) pour y ajouter le champ `whatsapp_message`.

## 2. API Backend (FastAPI)

- [x] 2.1 Mettre à jour les modèles Pydantic `CategoryOut` et `CategoryUpsertIn` dans [server.py](file:///apps/api/crm/server.py) pour inclure le champ optionnel `whatsapp_message: Optional[str] = None`.
- [x] 2.2 Créer un module d'import/export de catégories (ex: `crm/import_categories.py`) similaire à `crm/import_actes.py` en utilisant openpyxl.
- [x] 2.3 Ajouter la route `GET /api/categories/export` dans [server.py](file:///apps/api/crm/server.py) pour l'export Excel des catégories.
- [x] 2.4 Ajouter la route `POST /api/categories/import` dans [server.py](file:///apps/api/crm/server.py) pour l'import Excel des catégories.
- [x] 2.5 Ajouter la section `[whatsapp]` et le paramètre `message_repli` dans [config.py](file:///apps/api/src/config.py) pour charger le message de repli depuis `config.ini`.
- [x] 2.6 Mettre à jour `WhatsAppSettingsOut` et l'endpoint `GET /api/settings/whatsapp` dans [server.py](file:///apps/api/crm/server.py) pour renvoyer le message de repli (`fallback_message`).

## 3. Frontend (React)

- [x] 3.1 Mettre à jour les types TypeScript dans [schema.d.ts](file:///apps/web/src/api/schema.d.ts) (ou régénérer l'API si possible) et dans [types.ts](file:///apps/web/src/api/types.ts) pour y inclure `whatsapp_message` sur la catégorie.
- [x] 3.2 Ajouter les hooks de mutation pour `exportCategories` et `importCategories` dans [queries.ts](file:///apps/web/src/hooks/queries.ts).
- [x] 3.3 Intégrer l'action d'édition de la catégorie (y compris son message WhatsApp et sa couleur) dans [ModelesTab.tsx](file:///apps/web/src/screens/parametrage/ModelesTab.tsx) (bouton d'action à côté du titre de la catégorie ouvrant un `Sheet` d'édition).
- [x] 3.4 Ajouter les boutons "Importer les catégories" et "Exporter les catégories" en haut de [ModelesTab.tsx](file:///apps/web/src/screens/parametrage/ModelesTab.tsx) avec la boîte de dialogue de rapport d'importation.
- [x] 3.5 Mettre en œuvre le remplacement dynamique des variables (`<PRENOM>`, `<NOM>`, `<DOCUMENT>`) dans le lien de partage WhatsApp `open-wa-me` dans [DocumentsTab.tsx](file:///apps/web/src/screens/patient-detail/DocumentsTab.tsx) en chargeant le message WhatsApp de la catégorie du document, puis en se repliant sur le message de repli de l'API (configuré via `config.ini`) si aucun message personnalisé n'est configuré.
