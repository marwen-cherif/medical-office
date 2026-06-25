## ADDED Requirements

### Requirement: Catégorie en tant qu'attribut de modèle
Le système SHALL permettre d'associer une **catégorie en texte libre** à un modèle de
document, saisie dans l'application (dialogues « Nouveau modèle » et « Renommer le
modèle »), à côté du nom. La catégorie ne SHALL PAS être stockée dans le fichier `.docx` ;
elle SHALL être persistée côté application, associée au modèle par son nom. Un modèle SHALL
pouvoir n'avoir aucune catégorie.

#### Scenario: Saisie d'une catégorie à la création d'un modèle
- **WHEN** l'utilisateur crée un modèle et renseigne la catégorie `Radiologie`
- **THEN** le modèle est associé à la catégorie `Radiologie` en base

#### Scenario: Modèle sans catégorie
- **WHEN** l'utilisateur crée un modèle sans renseigner de catégorie
- **THEN** le modèle n'a aucune catégorie et continue de fonctionner comme aujourd'hui

#### Scenario: Catégorie conservée au renommage du modèle
- **WHEN** un modèle catégorisé `Ordonnances` est renommé
- **THEN** le modèle renommé reste associé à la catégorie `Ordonnances`

### Requirement: Suggestions de catégories à la saisie
Le champ catégorie SHALL proposer les catégories déjà connues comme suggestions tout en
restant libre : l'utilisateur SHALL pouvoir choisir une suggestion ou saisir une catégorie
nouvelle. Saisir une catégorie inconnue SHALL la créer.

#### Scenario: Réutilisation d'une catégorie existante
- **WHEN** la catégorie `Radiologie` existe déjà et que l'utilisateur ouvre le champ
  catégorie
- **THEN** `Radiologie` est proposée comme suggestion

#### Scenario: Création d'une nouvelle catégorie par saisie libre
- **WHEN** l'utilisateur saisit une catégorie inconnue `Parodontologie`
- **THEN** la catégorie `Parodontologie` est créée et associée au modèle

### Requirement: Catégorie identifiée visuellement (couleur et icône)
Chaque catégorie SHALL porter une couleur et une icône utilisées pour son repérage visuel
dans les listes de modèles et la fiche patient. Une catégorie nouvellement créée SHALL
recevoir une couleur par défaut, modifiable.

#### Scenario: Pastille de couleur/icône d'une catégorie
- **WHEN** des modèles sont affichés regroupés par catégorie
- **THEN** chaque groupe de catégorie affiche sa couleur et son icône

### Requirement: Renommage global d'une catégorie
Le système SHALL permettre de renommer une catégorie, en répercutant le nouveau nom sur
tous les modèles qui la portent. Le renommage SHALL conserver la couleur et l'icône.
Le système SHALL pouvoir, **en option et jamais par défaut**, répercuter le renommage sur
les documents déjà générés (mise à jour de leur catégorie et déplacement vers le nouveau
sous-dossier).

#### Scenario: Renommage répercuté sur les modèles
- **WHEN** la catégorie `Radio` est renommée en `Radiologie`
- **THEN** tous les modèles auparavant `Radio` sont désormais associés à `Radiologie`,
  couleur et icône conservées

#### Scenario: Documents existants non touchés par défaut
- **WHEN** une catégorie est renommée sans activer l'option de reclassement des documents
- **THEN** les documents déjà générés et leurs fichiers restent inchangés

### Requirement: Rangement des documents générés par catégorie
À la génération d'un document, le système SHALL ranger le fichier dans un sous-dossier de
catégorie du dossier patient : `output/<patient>/<categorie>/`, où le nom de sous-dossier
est dérivé de la catégorie par une transformation produisant un nom de dossier sûr (slug).
En l'absence de catégorie, le fichier SHALL être écrit à la racine du dossier patient
(comportement actuel). La convention de nom de fichier SHALL rester inchangée.

#### Scenario: Document rangé dans le sous-dossier de sa catégorie
- **WHEN** un document est généré depuis un modèle de catégorie `Radiologie`
- **THEN** le fichier est écrit dans `output/<patient>/radiologie/`

#### Scenario: Document sans catégorie rangé à la racine
- **WHEN** un document est généré depuis un modèle sans catégorie
- **THEN** le fichier est écrit à la racine du dossier patient `output/<patient>/`

### Requirement: Catégorie figée sur le document à la génération
Le système SHALL mémoriser la catégorie du modèle sur l'entrée `documents` au moment de la
génération (snapshot). Une modification ultérieure de la catégorie du modèle ne SHALL PAS
modifier rétroactivement la catégorie des documents déjà générés. La colonne SHALL être
additive et nullable ; les documents existants SHALL conserver une catégorie nulle sans
migration de données.

#### Scenario: Snapshot de la catégorie
- **WHEN** un document est généré depuis un modèle de catégorie `Notes d'honoraires`
- **THEN** l'entrée `documents` porte la catégorie `Notes d'honoraires`

#### Scenario: La catégorie du document ne suit pas le modèle
- **WHEN** la catégorie d'un modèle est changée après qu'un document a été généré
- **THEN** le document déjà généré conserve la catégorie qu'il avait à sa génération

#### Scenario: Préservation des documents existants à la mise à niveau
- **WHEN** une base de production est mise à niveau vers le nouveau schéma
- **THEN** les documents déjà présents conservent une catégorie nulle, et leurs fichiers
  ne sont ni déplacés ni régénérés

### Requirement: Regroupement des modèles par catégorie
L'écran de gestion des modèles SHALL regrouper les modèles par catégorie, avec la couleur
et l'icône de chaque catégorie. Les modèles sans catégorie SHALL être rassemblés dans un
groupe par défaut.

#### Scenario: Modèles groupés par catégorie
- **WHEN** des modèles de catégories `Radiologie` et `Ordonnances` existent
- **THEN** l'écran affiche un groupe `Radiologie` et un groupe `Ordonnances`, chacun
  listant ses modèles

#### Scenario: Modèles sans catégorie regroupés à part
- **WHEN** des modèles n'ont pas de catégorie
- **THEN** ils apparaissent dans un groupe par défaut distinct des catégories nommées

### Requirement: Regroupement des documents par catégorie dans la fiche patient
La fiche patient SHALL afficher les documents regroupés par catégorie, en sections
repliables affichant la couleur/icône et un compteur. Les documents sans catégorie SHALL
être rassemblés dans un groupe par défaut. À l'intérieur de chaque section, l'ordre
récent-d'abord existant SHALL être conservé.

#### Scenario: Documents groupés par catégorie sur la fiche
- **WHEN** un patient possède des documents de catégories `Radiologie` et `Ordonnances`
- **THEN** la fiche affiche une section `Radiologie` et une section `Ordonnances`, chacune
  avec son compteur et ses documents du plus récent au plus ancien

#### Scenario: Section « Sans catégorie »
- **WHEN** un patient possède des documents sans catégorie
- **THEN** ces documents apparaissent dans une section par défaut distincte
