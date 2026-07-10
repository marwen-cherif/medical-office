# activation-fonctionnalites

## Purpose

Gestion de l'activation/désactivation des fonctionnalités optionnelles du cabinet (feature flags) et conditionnement dynamique de la navigation et de l'interface utilisateur.
## Requirements
### Requirement: Contrôle d'activation des fonctionnalités

Le système SHALL stocker l'état d'activation de la fonctionnalité optionnelle WhatsApp API (`whatsapp_api_enabled`) sous forme de clé-valeur dans la table `meta` de la base de données. Il SHALL exposer cet état via les réglages de configuration WhatsApp retournés au client frontend et permettre son activation/désactivation dans un onglet dédié « Fonctionnalités » (Feature Flags).

#### Scenario: Récupération de l'état par défaut

- **WHEN** les réglages de configuration WhatsApp sont demandés alors qu'aucune valeur d'activation n'est enregistrée
- **THEN** le système retourne que la fonctionnalité est désactivée par défaut

#### Scenario: Mise à jour du statut d'activation

- **WHEN** l'utilisateur active ou désactive la fonctionnalité dans le paramétrage et enregistre
- **THEN** le système met à jour la valeur correspondante en base de données et retourne le nouvel état

### Requirement: Conditionnement de l'UI et de la Navigation WhatsApp API

Le système SHALL afficher l'onglet de paramétrage « WhatsApp » et le bouton « Envoyer par WhatsApp (Meta) » uniquement si la fonctionnalité `whatsapp_api_enabled` est activée dans les réglages de paramétrage de l'onglet « Fonctionnalités ». Si cette fonctionnalité est désactivée, l'onglet « WhatsApp » de la navigation latérale et le bouton d'envoi Meta Cloud SHALL être masqués de l'interface utilisateur.

#### Scenario: Affichage de l'onglet et du bouton quand activé

- **WHEN** le drapeau `whatsapp_api_enabled` est activé
- **THEN** le système affiche l'onglet de paramétrage « WhatsApp » dans la navigation latérale et affiche le bouton « Envoyer par WhatsApp (Meta) » sur les documents générés des patients avec téléphone

#### Scenario: Masquage de l'onglet et du bouton quand désactivé

- **WHEN** le drapeau `whatsapp_api_enabled` est désactivé
- **THEN** le système masque l'onglet de paramétrage « WhatsApp » de la navigation latérale et masque le bouton « Envoyer par WhatsApp (Meta) » sur les lignes de documents et fiches patients

