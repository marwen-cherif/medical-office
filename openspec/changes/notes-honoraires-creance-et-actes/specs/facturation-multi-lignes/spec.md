## ADDED Requirements

### Requirement: Montant de ligne propre à la note, distinct du montant de l'acte

Le **montant de chaque ligne adossée à un acte existant** d'une note multi-lignes SHALL être **modifiable** indépendamment, avec pour **valeur par défaut** le montant de l'acte correspondant. Le montant saisi sur la ligne SHALL être **purement d'affichage** : il alimente la
balise `<L_MONTANT>` et les **totaux calculés** de la note, et ne SHALL **jamais** modifier le
montant de l'acte sous-jacent ni la dette du patient (l'acte reste la source du dû). Le montant
réglé et le reste d'une ligne adossée à un acte SHALL continuer de **refléter l'acte** (lecture
seule). À la réouverture d'un brouillon, le montant **édité** de chaque ligne SHALL être restitué.

#### Scenario: Montant de note différent du montant de l'acte
- **WHEN** un acte de 950 est retenu dans une note et l'utilisateur saisit 600 comme montant de
  sa ligne, puis génère
- **THEN** la note affiche 600 sur cette ligne et dans ses totaux, tandis que l'acte conserve son
  montant 950 et que la dette du patient reste de 950

#### Scenario: Montant de ligne par défaut repris de l'acte
- **WHEN** un acte de 950 est retenu sans que l'utilisateur n'édite le montant de sa ligne
- **THEN** la ligne affiche 950 (valeur par défaut reprise de l'acte)

#### Scenario: Édition du montant de note sans effet sur la dette
- **WHEN** l'utilisateur modifie le montant d'une ligne adossée à un acte puis génère la note
- **THEN** le montant de l'acte et le total à recouvrer du patient restent inchangés

#### Scenario: Montant édité restitué à la réouverture du brouillon
- **WHEN** un brouillon où une ligne a été éditée à 600 (acte à 950) est rouvert
- **THEN** la ligne réaffiche 600 (le montant édité), pas 950

### Requirement: Initier une note d'honoraires depuis une sélection d'actes

Le système SHALL permettre d'**initier une note d'honoraires** directement depuis la **page
Actes/Plans** d'un patient, par deux points d'entrée : (1) **sélectionner plusieurs actes**
(isolés et/ou appartenant à des plans) puis lancer « Générer une note d'honoraires » pour la
sélection, et (2) une action **« Générer une note d'honoraires »** dans le **menu d'actions
(« ⋮ ») d'une ligne d'acte**, pour cet acte unique. Dans les deux cas, le dialogue de note SHALL
s'ouvrir **pré-rempli** avec les actes choisis **pré-cochés**, en réutilisant le flux multi-lignes
existant (sélection / désélection, montants éditables, totaux calculés). Ces points d'entrée ne
SHALL **pas** créer de nouvelle dette : les actes en restent la source.

#### Scenario: Note depuis une sélection multiple d'actes
- **WHEN** l'utilisateur coche deux actes isolés et un acte d'un plan sur la page Actes/Plans,
  puis lance « Générer une note d'honoraires »
- **THEN** le dialogue de note s'ouvre avec ces trois actes pré-cochés, prêt à générer

#### Scenario: Note depuis la ligne d'un acte
- **WHEN** l'utilisateur ouvre le menu d'actions « ⋮ » d'un acte et choisit « Générer une note
  d'honoraires »
- **THEN** le dialogue de note s'ouvre avec ce seul acte pré-coché

#### Scenario: Génération depuis actes sans nouvelle dette
- **WHEN** une note est générée depuis des actes sélectionnés sur la page Actes/Plans
- **THEN** aucune créance « note » n'est créée et le total à recouvrer du patient reste celui de
  ses actes

## REMOVED Requirements

### Requirement: Aucun paiement créé à la génération

**Reason** : La règle de création de dette par une note est désormais **centralisée** et rendue
**conditionnelle** dans `plans-de-traitement` › « Source unique du dû (pas de double-comptage) » :
une note **adossée à des actes** reste sans paiement, tandis qu'une note **autonome** crée une
créance « note ». Conserver ici une règle « aucun paiement » **absolue** contredirait ce nouveau
comportement.

**Migration** : Aucune migration de données. Le comportement des notes **adossées à des actes**
est inchangé (aucun paiement créé, total servant uniquement d'affichage/email, nouveaux actes
créés comme `prestations`). Seules les notes **autonomes** (sans acte rattaché) créent désormais
une créance « note » à la génération, conformément à la règle conditionnelle de
`plans-de-traitement`.
