## Context

Le CRM stocke des montants « libres » sur `documents.montant` et `paiements.montant`,
sans aucune référence de prix. Les prochaines fonctionnalités (`plans-de-traitement`,
`facturation-multi-lignes`) doivent **pré-remplir** des montants à partir d'un acte
choisi. On a donc besoin d'un **catalogue d'actes tarifés** simple, autonome et
réutilisable.

Le code offre déjà tout le patron nécessaire : la table `categories` (créée
paresseusement, attributs visuels, renommage global) et les onglets de Paramétrage
*Modèles* / *Modèles d'email* (`show_templates`, `show_mail_templates`) montrent le
schéma CRUD + recherche + pagination (`_pagination`, `_card`, `_show_dialog`,
`_search_field`, `PAGE_SIZE`). Ce change **réutilise** ce patron plutôt que d'en inventer
un nouveau.

Contraintes structurantes (CLAUDE.md) : schéma **expand-only**, non destructif, avec bump
`SCHEMA_VERSION` + migration idempotente gardée + snapshot pré-migration ; toute évolution
suppose une base de production existante et peuplée.

## Goals / Non-Goals

**Goals :**

- Une table `actes` autonome : libellé, prix, `actif`, ordre d'affichage (+ code
  optionnel).
- Un onglet *Paramétrage › Actes* : recherche, liste paginée, création, édition, retrait
  (désactivation) — calque des onglets existants.
- Un **contrat de lecture** clair (liste/recherche paginée, lookup par id) que d'autres
  fonctionnalités pourront consommer.
- Retrait **non destructif** d'un acte (préserve tout référencement futur).
- Migration **purement additive**.

**Non-Goals :**

- **Pas de consommation** du référentiel dans ce change : le pré-remplissage des
  paiements, des étapes de plan ou des lignes de facture est porté par
  `plans-de-traitement` / `facturation-multi-lignes`.
- **Pas de familles / regroupement d'actes** en v1 (liste plate ; le champ `code`
  optionnel suffit au repérage). Évolution possible plus tard.
- **Pas de devise ni de TVA** stockées : le prix est un `REAL` simple, cohérent avec
  `documents.montant` / `depenses.montant`, formaté via `format_montant`.
- **Pas d'historique de prix** (versionnement des tarifs) : un acte porte son prix
  courant ; les consommateurs en figent une copie (snapshot) à l'usage.

## Decisions

### D1 — Table `actes` autonome, clé technique `id`

Nouvelle table `actes(id, libelle, prix, code, actif, sort_order, created_at)`. On utilise
une **clé technique `id` auto-incrémentée** (et non le libellé comme clé naturelle, à la
différence de `categories`), parce qu'un libellé peut être édité et qu'un référencement
historique doit rester stable même après renommage.

- *Alternative écartée* : réutiliser/étendre `categories` — sémantique différente (une
  catégorie n'a pas de prix et sert au regroupement visuel des modèles) ; mélanger les
  deux nuirait à la lisibilité.

### D2 — Retrait = désactivation (`actif`), jamais suppression dure par défaut

Retirer un acte le passe `actif = 0` : il **disparaît des listes de saisie** mais reste en
base. Cela protège tout futur snapshot (une étape de plan / une ligne de facture ayant
copié cet acte) et permet de réactiver. Une suppression **dure** reste possible
uniquement pour un acte jamais utilisé (décision de l'appelant), mais l'UI par défaut
propose la désactivation.

### D3 — Prix `REAL` sans devise, formaté `format_montant`

`prix` est un `REAL`. Pas de colonne devise/TVA (cohérent avec l'existant). L'affichage
réutilise `format_montant` (espace milliers, virgule décimale).

### D4 — Recherche + pagination SQL identiques au reste de l'app

`list_actes(search, actif_seulement, limit, offset)` + `count_actes(...)`, recherche
insensible aux accents sur le libellé (même approche `slugify`/`LIKE` que patients/
documents). Pagination `LIMIT/OFFSET`, `PAGE_SIZE = 12`, contrôles `_pagination`.

### D5 — Contrat de lecture pour le pré-remplissage (sans couplage)

Le référentiel expose `list_actes(...)` (saisie/recherche) et `get_acte(conn, id)`
(lookup). Le **contrat** offert aux consommateurs est : *un acte fournit un `(libelle,
prix)` que le consommateur copie (snapshot) au moment de l'usage*. La manière de
consommer (quelles tables snapshotent, comment) appartient aux changes consommateurs.
Documenté ici uniquement pour cadrer l'interface ; **aucun appelant n'est implémenté dans
ce change**.

## Risks / Trade-offs

- **Désactivation vs suppression** : un acte désactivé encombre potentiellement la base à
  long terme. → *Mitigation* : filtre `actif` par défaut dans les listes de saisie ; vue
  « inclure les inactifs » pour la gestion.
- **Doublons de libellé** : la clé technique autorise deux actes de même libellé. →
  *Mitigation* : avertissement (non bloquant) à la création si un libellé actif identique
  existe déjà ; pas de contrainte d'unicité dure (un cabinet peut légitimement vouloir
  deux variantes).
- **Migration sur base de production** : → *Mitigation* : table nullable/additive,
  migration idempotente gardée (`CREATE TABLE IF NOT EXISTS`), **snapshot pré-migration**,
  anti-downgrade déjà en place ; test sur copie réelle de `cabinet.db`.

## Migration Plan

1. **Schéma** : ajouter `CREATE TABLE IF NOT EXISTS actes (...)` à `_SCHEMA` ; comme
   `executescript` ne fait pas d'`ALTER`, la table est créée à l'ouverture sur toute base.
   Aucune étape `_migrate()` de transformation de données n'est nécessaire (table neuve).
   Bumper `SCHEMA_VERSION` 8 → 9.
2. **Sauvegarde** : le **snapshot pré-migration** labellisé est déjà déclenché par
   `connect()` dès que la version disque est inférieure (mécanique existante).
3. **Déploiement** : nouvelle `.exe` posée à côté des données existantes ; à l'ouverture,
   création transparente de la table ; aucun document/paiement existant modifié.
4. **Rollback** : anti-downgrade (`SchemaTooNewError`) déjà en place ; en cas de problème,
   restaurer le snapshot pré-migration. Aucune donnée détruite (purement additif).
5. **Validation pré-livraison** (manuelle) : copier un `cabinet.db` de `backups/`, lancer
   la nouvelle build, vérifier que patients/documents/paiements se chargent et que
   l'onglet *Actes* permet de créer/éditer/désactiver/rechercher.

## Open Decisions

- **`code` d'acte** — *proposé* : colonne optionnelle nullable pour un code interne
  (repérage rapide), non obligatoire en v1. À confirmer si utile.
- **Familles d'actes** — *reporté hors v1* (liste plate). À rouvrir si le catalogue
  devient long.
- **Avertissement de doublon de libellé** — *proposé non bloquant*. À confirmer.
