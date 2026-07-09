"""Couche IA decouplee : provider abstrait + factory, configurable par fonctionnalite.

Une fonctionnalite (ex. extraction du montant d'une facture) declare dans config.ini
quel provider elle utilise et quel prompt elle applique ; le factory instancie le bon
provider. Ajouter un provider ou une fonctionnalite = une classe / une section de config,
sans toucher au code appelant. Voir spec_technique_depenses.md (section 3).
"""
