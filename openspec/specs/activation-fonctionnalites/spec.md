# activation-fonctionnalites

## Purpose

Gestion de l'activation/désactivation des fonctionnalités optionnelles du cabinet (feature flags) et conditionnement dynamique de la navigation et de l'interface utilisateur.
## Requirements
### Requirement: Contrôle d'activation des fonctionnalités

Le système SHALL stocker l'état d'activation des fonctionnalités optionnelles (WhatsApp API `whatsapp_api_enabled` et Emailing `emailing_enabled`) sous forme de clé-valeur dans la table `meta` de la base de données. Il SHALL exposer ces états via un endpoint dédié aux fonctionnalités (`/api/settings/features`) retourné au client frontend et permettre leur activation/désactivation dans un onglet dédié « Fonctionnalités » (Feature Flags).

#### Scenario: Récupération de l'état par défaut

- **WHEN** les réglages des fonctionnalités sont demandés alors qu'aucune valeur d'activation n'est enregistrée
- **THEN** le système retourne que WhatsApp API est désactivé par défaut et que l'Emailing est activé par défaut

#### Scenario: Mise à jour du statut d'activation

- **WHEN** l'utilisateur active ou désactive une fonctionnalité dans le paramétrage et enregistre
- **THEN** le système met à jour la valeur correspondante en base de données et retourne le nouvel état

### Requirement: Conditionnement de l'UI et de la Navigation WhatsApp API

Le système SHALL afficher l'onglet de paramétrage « WhatsApp » et le bouton « Envoyer par WhatsApp (Meta) » uniquement si la fonctionnalité `whatsapp_api_enabled` est activée dans les réglages de paramétrage de l'onglet « Fonctionnalités ». Si cette fonctionnalité est désactivée, l'onglet « WhatsApp » de la navigation latérale et le bouton d'envoi Meta Cloud SHALL être masqués de l'interface utilisateur.

#### Scenario: Affichage de l'onglet et du bouton quand activé

- **WHEN** le drapeau `whatsapp_api_enabled` est activé
- **THEN** le système affiche l'onglet de paramétrage « WhatsApp » dans la navigation latérale et affiche le bouton « Envoyer par WhatsApp (Meta) » sur les documents générés des patients avec téléphone

#### Scenario: Masquage de l'onglet et du bouton quand désactivé

- **WHEN** le drapeau `whatsapp_api_enabled` est désactivé
- **THEN** le système masque l'onglet de paramétrage « WhatsApp » de la navigation latérale et masque le bouton « Envoyer par WhatsApp (Meta) » sur les lignes de documents et fiches patients

### Requirement: Conditionnement de l'UI et de la Navigation Emailing

Le système SHALL afficher l'onglet de paramétrage « Modèles d'email » et le bouton « Envoyer par email » uniquement si la fonctionnalité `emailing_enabled` est activée dans les réglages de paramétrage de l'onglet « Fonctionnalités ». Si cette fonctionnalité est désactivée, l'onglet « Modèles d'email » de la navigation du paramétrage et le bouton d'envoi d'email SHALL être masqués de l'interface utilisateur.

#### Scenario: Affichage de l'onglet et du bouton quand activé

- **WHEN** le drapeau `emailing_enabled` est activé
- **THEN** le système affiche l'onglet de paramétrage « Modèles d'email » dans le paramétrage et affiche le bouton « Envoyer par email » sur les documents générés

#### Scenario: Masquage de l'onglet et du bouton quand désactivé

- **WHEN** le drapeau `emailing_enabled` est désactivé
- **THEN** le système masque l'onglet de paramétrage « Modèles d'email » dans le paramétrage et masque le bouton « Envoyer par email » sur les lignes de documents et fiches patients

### Requirement: Blocage backend de l'envoi d'email

Le système SHALL lever une erreur et bloquer l'envoi d'email si la fonctionnalité `emailing_enabled` est désactivée.

#### Scenario: Tentative d'envoi d'email quand désactivé

- **WHEN** une requête d'envoi d'email est reçue et le drapeau `emailing_enabled` est désactivé
- **THEN** le système bloque l'envoi et retourne une erreur de type 400 Bad Request

