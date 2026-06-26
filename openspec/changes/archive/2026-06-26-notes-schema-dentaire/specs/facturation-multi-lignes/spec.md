## MODIFIED Requirements

### Requirement: Contexte de variables standard prédéfini

Le système SHALL exposer aux modèles un **contrat de balises fixe et documenté**, sans
configuration de colonnes par modèle : des **balises document** (champs patient, date
d'émission ; totaux `<TOTAL_DU>`, `<TOTAL_REGLE>`, `<RESTE_A_PAYER>`, `<NB_ACTES>` ; **dents
agrégées** `<DENTS>`, `<NB_DENTS>` ; **schéma dentaire** `<ODONTOGRAMME>`) et des **balises de
ligne** préfixées `L_` (`<L_DATE>`, `<L_ACTE>`, `<L_DENTS>`, `<L_NOTE>`, `<L_MONTANT>`,
`<L_REGLE>`, `<L_RESTE>`). `<DENTS>` (liste FDI agrégée) et `<NB_DENTS>` (nombre de dents
distinctes) SHALL être des balises **texte** ; `<ODONTOGRAMME>` SHALL être une balise **image**
remplacée par un schéma dentaire. La sémantique d'agrégation des dents et le rendu de l'image
relèvent de la capacité `schema-dentaire-notes`. Un modèle SHALL être considéré « note
multi-lignes » s'il contient au moins une balise de ligne `L_*`, et « simple » sinon ; les
balises document `<DENTS>`, `<NB_DENTS>` et `<ODONTOGRAMME>` SHALL être disponibles **aussi
bien** pour une note multi-lignes que pour une note simple.

#### Scenario: Détection d'un modèle « note multi-lignes »

- **WHEN** un modèle contient au moins une balise `<L_*>` dans une cellule de tableau
- **THEN** le système le traite comme une note multi-lignes et son bloc de lignes est répété
  par les lignes retenues

#### Scenario: Modèle simple inchangé

- **WHEN** un modèle ne contient aucune balise `<L_*>`
- **THEN** il est traité comme « simple » et son rendu est identique à celui d'avant ce
  changement (une valeur par balise, aucun bloc répétable)

#### Scenario: Balises du contrat disponibles sans configuration

- **WHEN** l'auteur d'un modèle place `<L_DATE>`, `<L_ACTE>`, `<L_MONTANT>` et `<TOTAL_DU>`
- **THEN** ces balises sont remplies à la génération sans qu'aucune colonne n'ait été
  configurée pour ce modèle

#### Scenario: Balises dents agrégées disponibles dans le contrat

- **WHEN** l'auteur d'un modèle place `<DENTS>`, `<NB_DENTS>` et `<ODONTOGRAMME>` dans un
  modèle de note (simple ou multi-lignes)
- **THEN** ces balises sont reconnues comme des balises document du contrat et remplies à la
  génération sans configuration de colonnes, `<DENTS>`/`<NB_DENTS>` en texte et
  `<ODONTOGRAMME>` par un schéma dentaire (image)
