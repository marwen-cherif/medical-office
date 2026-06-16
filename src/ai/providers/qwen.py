"""Provider vision Qwen-VL-OCR (Alibaba DashScope), via l'endpoint OpenAI-compatible.

HTTP avec `requests` (deja dependance du projet) : aucune dependance ajoutee. L'image est
envoyee dans un bloc `image_url` (data-URL base64). On ne s'appuie pas sur `response_format`
(support variable sur les modeles VL) : le prompt impose le JSON et on le parse de facon
tolerante.
"""

from __future__ import annotations

import json
import re

import requests

from ..base import AIError, AIProvider, ImagePart
from ..log import log_ai

_DEFAULT_BASE = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


def _data_url(part: ImagePart) -> str:
    return f"data:{part.media_type};base64,{part.data_b64}"


def _extract_json(text: str) -> dict:
    """Parse le 1er objet JSON trouve, meme entoure de ```json ... ``` ou de texte."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise AIError(f"Pas de JSON dans la reponse: {text[:120]}")
    try:
        return json.loads(match.group(0))
    except ValueError as exc:
        raise AIError(f"JSON invalide: {exc}") from exc


class QwenVisionProvider(AIProvider):
    name = "qwen"
    supports_vision = True

    def complete_json(self, *, system, user, images=None, max_tokens=512):
        base = (self.cfg.base_url or _DEFAULT_BASE).rstrip("/")
        url = f"{base}/chat/completions"
        model = self.cfg.model or "qwen-vl-ocr"
        content: list[dict] = [{"type": "text", "text": user}]
        for img in images or []:
            content.append({"type": "image_url", "image_url": {"url": _data_url(img)}})
        # Trace l'intention (sans la cle ni les donnees image, qui seraient enormes).
        log_ai("QWEN_REQUEST", url=url, model=model, images=len(images or []),
               max_tokens=max_tokens)
        try:
            resp = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.cfg.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": content},
                    ],
                    "max_tokens": max_tokens,
                    "stream": False,
                },
                timeout=60,  # vision : images = payload plus lourd
            )
        except requests.RequestException as exc:
            log_ai("QWEN_NETWORK_ERROR", url=url, error=str(exc))
            raise AIError(f"Qwen reseau: {exc}") from exc
        if resp.status_code != 200:
            # Le corps de l'erreur dit pourquoi (404 route, 401 cle, 400 schema/modele...).
            log_ai("QWEN_HTTP_ERROR", url=url, status=resp.status_code, body=resp.text[:600])
            raise AIError(f"Qwen HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            text = resp.json()["choices"][0]["message"]["content"]
        except (KeyError, ValueError, IndexError, TypeError) as exc:
            log_ai("QWEN_BAD_SHAPE", url=url, status=resp.status_code,
                   body=resp.text[:600], error=str(exc))
            raise AIError(f"Qwen reponse invalide: {exc}") from exc
        # Trace la reponse brute du modele (tronquee) avant parsing du JSON.
        log_ai("QWEN_RESPONSE", status=resp.status_code, content=text[:600])
        return _extract_json(text)
