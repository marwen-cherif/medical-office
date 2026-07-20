# whatsapp-document-templates Specification

## Purpose
TBD - created by archiving change whatsapp-document-templates. Update Purpose after archive.
## Requirements
### Requirement: Configuration du message WhatsApp par catégorie
Le système SHALL permettre à l'utilisateur de configurer un message WhatsApp personnalisé pour chaque catégorie de documents (ex. "Facturation", "Ordonnances") enregistrée dans l'application. Ce message peut comporter des balises de fusion telles que `<PRENOM>`, `<NOM>`, `<DOCUMENT>` pour personnaliser le texte lors de l'envoi.

#### Scenario: Enregistrement d'un message WhatsApp pour une catégorie
- **WHEN** l'utilisateur saisit un message personnalisé (ex: "Bonjour <PRENOM> <NOM>, voici votre <DOCUMENT>.") pour la catégorie "Facturation" et clique sur Enregistrer
- **THEN** le système associe et sauvegarde ce message avec la catégorie en base de données

#### Scenario: Suppression du message WhatsApp d'une catégorie
- **WHEN** l'utilisateur vide le champ de message WhatsApp personnalisé pour la catégorie "Facturation" et enregistre
- **THEN** le système supprime le message WhatsApp associé à cette catégorie en base de données, activant ainsi le comportement de repli global pour cette catégorie

### Requirement: Envoi de document via wa.me avec message dynamique par catégorie
Lorsqu'un utilisateur initie l'action d'ouverture de WhatsApp (wa.me) pour envoyer un document à un patient, le système SHALL charger le message WhatsApp configuré pour la catégorie du modèle de ce document et remplacer de manière dynamique les balises de fusion par les informations réelles avant d'ouvrir le lien wa.me.

#### Scenario: Envoi d'un document dont la catégorie a un message configuré
- **WHEN** l'utilisateur clique sur "Ouvrir dans WhatsApp (wa.me)" pour un document dont la catégorie est "Facturation", cette catégorie ayant le message configuré "Bonjour <PRENOM> <NOM>, voici votre <DOCUMENT>."
- **THEN** le système ouvre l'URL `wa.me` avec le numéro du patient et le texte pré-rempli : "Bonjour Jean Dupont, voici votre note d'honoraires."

#### Scenario: Envoi d'un document sans catégorie ou sans message configuré
- **WHEN** l'utilisateur clique sur "Ouvrir dans WhatsApp (wa.me)" pour un document sans catégorie ou dont la catégorie n'a pas de message personnalisé configuré
- **THEN** le système utilise le message de repli configuré dans le fichier config.ini (ex: "Bonjour <PRENOM> <NOM>, voici votre <DOCUMENT>.") en remplaçant correctement les variables

### Requirement: Import/Export de la configuration des catégories
Le système SHALL proposer une fonctionnalité d'import et d'export en masse de la configuration des catégories au format Excel (.xlsx), comprenant le nom de la catégorie, sa couleur, son icône, son ordre de tri et son message WhatsApp personnalisé.

#### Scenario: Exportation des catégories vers Excel
- **WHEN** l'utilisateur clique sur "Exporter" dans le volet d'import/export des catégories
- **THEN** le système génère un classeur Excel `.xlsx` listant toutes les catégories existantes avec leurs colonnes : Nom, Couleur, Icone, Ordre, Message WhatsApp, et ouvre le fichier dans l'application système par défaut

#### Scenario: Importation réussie d'un fichier Excel de catégories
- **WHEN** l'utilisateur importe un classeur Excel valide contenant des modifications sur les catégories
- **THEN** le système met à jour ou crée les catégories correspondantes en base de données et affiche un compte-rendu affichant le nombre de catégories créées ou mises à jour

