"""Interface commune des providers IA + types partages."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config import AIProviderCfg


class AIError(RuntimeError):
    """Toute defaillance d'un provider IA (reseau, auth, quota, reponse invalide)."""


@dataclass
class ImagePart:
    """Une image a soumettre a un provider vision (base64)."""
    media_type: str   # "image/png" | "image/jpeg"
    data_b64: str


class AIProvider(ABC):
    """Provider IA : une seule operation (completion JSON), texte et/ou image.

    `supports_vision` indique si le provider peut lire des images ; le factory et les
    fonctionnalites s'en servent pour router (une fonctionnalite vision exige True).
    """

    name: str = ""
    supports_vision: bool = False

    def __init__(self, cfg: "AIProviderCfg") -> None:
        self.cfg = cfg

    @abstractmethod
    def complete_json(
        self,
        *,
        system: str,
        user: str,
        images: "list[ImagePart] | None" = None,
        max_tokens: int = 512,
    ) -> dict:
        """Renvoie un dict JSON. Leve AIError en cas d'echec."""
        raise NotImplementedError
