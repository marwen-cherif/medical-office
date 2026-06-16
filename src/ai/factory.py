"""Factory : registre des providers + resolution du provider d'une fonctionnalite."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import AIError, AIProvider
from .providers.qwen import QwenVisionProvider

if TYPE_CHECKING:
    from src.config import AIProviderCfg, Config

# Registre des providers connus. Ajouter une entree (et le fichier providers/<x>.py)
# pour brancher un nouveau fournisseur — rien d'autre a changer cote appelant.
_REGISTRY: dict[str, type[AIProvider]] = {
    "qwen": QwenVisionProvider,
    # "gemini": GeminiProvider, "anthropic": AnthropicProvider,  # a enregistrer quand ajoutes
}


def register_provider(name: str, cls: type[AIProvider]) -> None:
    _REGISTRY[name] = cls


def build_provider(pcfg: "AIProviderCfg") -> AIProvider:
    cls = _REGISTRY.get(pcfg.name)
    if cls is None:
        raise AIError(f"Provider IA inconnu: {pcfg.name!r}")
    return cls(pcfg)


def provider_for_feature(cfg: "Config", feature: str) -> "AIProvider | None":
    """Provider configure pour une fonctionnalite, ou None si l'IA est indisponible.

    Indisponible = fonctionnalite absente/desactivee, provider inconnu, ou cle d'API vide.
    """
    feat = cfg.ai.feature(feature)
    if feat is None or not feat.enabled:
        return None
    pcfg = cfg.ai.provider(feat.provider)
    if pcfg is None or not pcfg.api_key.strip():
        return None
    try:
        return build_provider(pcfg)
    except AIError:
        return None
