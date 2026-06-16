# Cabinet Aslem - CRM & generateur de notes d'honoraires

Application Windows (interface graphique **Flet**, en fenetre bureau ou dans le
navigateur) pour le cabinet du Dr Aslem Gouiaa. Elle gere un referentiel local de
patients et, pour chacun, genere des documents (notes d'honoraires, etc.) au format
**JPG ou PDF** a partir de modeles Word, puis les envoie par email via **Mailjet** et
suit l'ouverture des mails.

Les donnees sont stockees dans une base **SQLite locale** (`data/cabinet.db`) — aucun
cloud.

## Prerequis

- Windows 10 ou 11
- Microsoft Word installe (utilise via COM pour rendre les modeles)
- Python 3.11 ou plus recent (uniquement pour le dev / build, pas pour l'execution de
  l'exe distribue)
- Un compte Mailjet (https://app.mailjet.com) avec :
  - une cle API + cle secrete (Account -> API Key Management)
  - une adresse d'expediteur **validee** dans Mailjet

## Configuration (`config.ini`)

Editer `config.ini` :

- `mailjet.api_key` et `mailjet.api_secret` (depuis le dashboard Mailjet)
- `mailjet.from_email` : doit etre une adresse validee dans Mailjet
- `mailjet.from_name` : nom affiche dans le From
- `mailjet.sandbox = true` pour tester sans envoyer reellement
- `paths.output_format` : `jpg` (defaut) ou `pdf` selon le format des documents
- `mail.template_id` : ID du template transactionnel Mailjet utilise pour l'email (le
  contenu/design est gere dans Mailjet). Variables disponibles dans le template :
  `{{var:prenom}}`, `{{var:nom}}`, `{{var:montant}}`, `{{var:acte}}`, `{{var:date}}`,
  `{{var:type_document}}`. `mail.subject` (optionnel) surcharge le sujet du template.

> `config.ini` contient des cles API Mailjet : a traiter comme des secrets. Le fichier est
> git-ignore (jamais versionne) — ne pas le retirer du `.gitignore`.

## Lancer l'application

**Avec Python (dev)** : double-cliquer sur `run-crm.bat` (ou `python crm_app.py`).
Pour la version navigateur : `run-crm-web.bat` (ou `python crm_web.py`).

**Via .exe (utilisateur non technique)** : voir
[Build des executables](#build-des-executables) plus bas. Deux executables sont
produits :

- **`Cabinet-CRM.exe`** : ouvre l'application dans sa propre fenetre (mode bureau).
- **`Cabinet-CRM-Web.exe`** : demarre l'app et l'ouvre dans le navigateur (Chrome).
  Une petite fenetre noire reste ouverte : la **garder ouverte** pendant l'utilisation,
  la **fermer** arrete l'application. Pour acceder depuis un autre appareil du reseau
  (tablette, autre PC), lancer avec la variable `CRM_HOST=0.0.0.0` puis ouvrir
  `http://IP-DU-PC:8550` sur l'autre appareil (`CRM_PORT` change le port, defaut 8550).

## Ce que l'app permet

- **Patients avec identifiant stable** : on saisit un patient une fois, il recoit un
  `id`. Si on resaisit un nom+prenom deja connu, l'app le **detecte** et propose de
  reutiliser la fiche existante (c'est l'utilisateur qui confirme, pour gerer les
  homonymes).
- **Plusieurs types de documents** : chaque type est un modele Word dans `templates/`.
  Depuis l'ecran *Modeles*, on cree un modele et on l'**edite dans Word** (l'app ouvre
  Word). Generation au format JPG ou PDF selon `paths.output_format`.
- **Variables dynamiques par modele** : l'app **detecte les balises** `<...>` du Word.
  Les balises `<NOM>`, `<PRENOM>`, `<EMAIL>`, `<TELEPHONE>`, `<ADRESSE>`,
  `<DATE_NAISSANCE>` sont remplies automatiquement depuis la fiche patient ; les autres
  (ex. `<NB_SEANCES>`, `<MOTIF>`, `<MONTANT>`, `<DATE>`, `<ACTE>`) sont demandees a la
  generation. Le bouton **« Configurer les variables »** (page *Modeles*) permet de
  definir, par modele, le libelle, le type (texte / nombre / date) et la valeur par
  defaut de chaque balise. Ajouter une balise dans le Word suffit a creer une variable.
- **Referentiel local** : pour chaque patient, l'historique des documents generes /
  envoyes (avec statut Mailjet) et le suivi des **paiements en attente / encaisses**.
- **Modeles d'email** (onglet *Emails*) : on associe un nom lisible a l'ID d'un template
  transactionnel Mailjet ; a l'envoi, on choisit le modele dans une liste deroulante. Les
  champs date utilisent un calendrier (date picker) et les boutons longs (generation,
  envoi) affichent un indicateur de chargement pour eviter les doubles-clics.

> Donnees de sante = **RGPD** : la base reste strictement locale. Pensez a sauvegarder
> regulierement le fichier `data/cabinet.db` et a en proteger l'acces. L'app fait aussi
> une copie horodatee dans `backups/` a chaque demarrage (les 10 dernieres conservees).

## Suivi des statuts d'envoi (Mailjet)

Apres l'envoi, l'app interroge Mailjet pour rapatrier le statut de chaque message :

`sent`, `opened`, `clicked`, `bounce`, `hardbounced`, `spam`, `unsub`, `blocked`,
`queued`, `softbounced`. Les statuts `clicked`, `bounce`, `hardbounced`, `spam`,
`unsub`, `blocked` sont consideres comme **finaux** et ne sont plus rafraichis.

## Remise a zero (vider la base)

Pour repartir d'une base vierge (par exemple apres les tests) : double-cliquer sur
`reset.bat` (ou `python -m crm.reset`). La commande :

- **demande une confirmation** (il faut taper `SUPPRIMER`) ;
- vide toutes les tables de `data/cabinet.db` et remet les compteurs d'`id` a zero ;
- supprime les notes generees (`.jpg` / `.pdf`) dans `output/` ;
- **conserve** `templates/` et `config.ini`.

Au prochain lancement, l'app demarre sur une base vide. Pour un script automatise sans
question : `python -m crm.reset --yes`.

> Action **irreversible**. Faites une copie de `data/cabinet.db` avant si besoin.

## Build des executables

Double-cliquer sur **`build-crm.bat`**. Le script installe les dependances puis
produit, dans le dossier `dist\`, **deux executables autonomes** (Python n'est pas
requis sur le poste de l'utilisateur final) :

- `dist\Cabinet-CRM.exe` — application **bureau** (fenetre native).
- `dist\Cabinet-CRM-Web.exe` — application **web** (s'ouvre dans le navigateur).

Le build copie aussi `config.ini` a cote des exes. Les dossiers `data\`, `templates\`
et `output\` sont crees automatiquement a cote des exes au premier lancement.
**A distribuer ensemble** : les deux `.exe` + `config.ini` (et `templates\` si on veut
preremplir des modeles).

> Le build se fait sur une machine **Windows avec Microsoft Word installe** (le moteur
> de generation pilote Word).

## Lancer en dev (sans build)

Depuis le dossier du projet :

```
python -m pip install -r requirements.txt
python crm_app.py        # fenetre bureau
python crm_web.py        # navigateur
```

## Depannage

- **"Word.Application introuvable"** : Microsoft Word n'est pas installe.
- **Erreur 401 Mailjet** : verifier `api_key` / `api_secret` dans `config.ini`.
- **Erreur "From email not validated"** : valider l'adresse d'expediteur dans le
  dashboard Mailjet (Account -> Sender domains & addresses).
- **Pour forcer la regeneration d'un document** : supprimer le fichier `output\...`
  (`.jpg` / `.pdf`) correspondant et la ligne du document dans l'app, puis relancer la
  generation.
- **Changer `output_format`** regenere les documents au nouveau format (le nom de
  fichier change d'extension, donc les anciens ne sont pas reconnus).
