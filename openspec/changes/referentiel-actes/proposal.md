## Why

Le CRM n'a aujourd'hui **aucun catalogue d'actes ni de tarifs**. Chaque montant est
saisi à la main (`documents.montant`, `paiements.montant`), ce qui expose à des prix
incohérents d'un patient à l'autre et à de la ressaisie. Or deux fonctionnalités en
préparation ont besoin d'une **source de prix réutilisable** pour pré-remplir des
montants : les **plans de traitement** (change `plans-de-traitement`, à venir) — où
chaque étape « acte » reprend un acte tarifé — et la **facturation multi-lignes**
(`facturation-multi-lignes`) — où chaque ligne d'une note récapitulative porte un acte
et un montant.

Plutôt que de loger ce catalogue dans l'un de ces changes (et l'alourdir), on
l'introduit comme un **référentiel autonome**, réutilisable, livrable indépendamment.

## What Changes

- **Nouvelle table `actes`** : un référentiel d'actes tarifés (libellé + prix), avec un
  indicateur `actif` (retrait sans perte) et un ordre d'affichage.
- **Nouvel onglet « Actes » dans Paramétrage** : recherche + liste paginée + création /
  édition / désactivation d'un acte — **calque** des onglets *Modèles* et *Modèles
  d'email* existants (mêmes helpers : pagination, cartes, dialogues, recherche).
- **Suppression non destructive** : retirer un acte le marque **inactif** (il disparaît
  des listes de saisie) sans casser un éventuel historique qui l'aurait référencé.
- **Contrat de lecture** exposé par `crm/repo.py` (liste/recherche paginée, lookup) que
  d'autres fonctionnalités pourront consommer pour **pré-remplir** un montant. La
  consommation elle-même (paiements, étapes de plan, lignes de facture) est **hors
  périmètre** de ce change : elle reste portée par `plans-de-traitement` /
  `facturation-multi-lignes`.
- **Aucune migration destructive** : table additive, schéma expand-only.

## Capabilities

### New Capabilities

- `referentiel-actes` : catalogue d'actes tarifés (libellé, prix, actif, ordre), avec
  CRUD + recherche + pagination dans un onglet de Paramétrage, retrait non destructif, et
  une API de lecture réutilisable pour pré-remplir des montants ailleurs dans
  l'application.

### Modified Capabilities

<!-- Aucune capability formalisée n'existe encore dans openspec/specs/. Le comportement
     de saisie manuelle des montants (documents/paiements) reste inchangé : pas de delta
     de capability existante. -->

## Impact

- **Schéma SQLite (`crm/db.py`)** : nouvelle table `actes` via
  `CREATE TABLE IF NOT EXISTS`, bump de `SCHEMA_VERSION` (8 → 9) + étape `_migrate()`
  idempotente, **snapshot pré-migration** (règles de préservation des données, cf.
  CLAUDE.md). Purement additif, aucune donnée existante touchée.
- **`crm/repo.py`** : dataclass `Acte` + CRUD (création, édition, activation/
  désactivation) + liste/recherche paginée (`list_actes` / `count_actes`) + lookup par id.
- **`crm/app.py`** : nouvel onglet *Paramétrage › Actes* (réutilise `_pagination`,
  `_card`, `_show_dialog`, `_btn`, `_search_field`, `PAGE_SIZE`).
- **Moteur partagé (`src/`)** : **non modifié** ; pas de Word, pas de Mailjet.
- **Données** : 100 % additif ; aucun fichier généré ni note existante affectés.
- **Séquencement** : ce change prend `SCHEMA_VERSION` v9 ; `plans-de-traitement`, qui le
  consomme, suivra avec la version suivante.
