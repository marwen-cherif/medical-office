from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import requests

API_VERSION = "v20.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"


def _log_path() -> Path:
    base = (
        Path(sys.executable).parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent.parent
    )
    log_dir = base / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "whatsapp.log"


def log_whatsapp(event: str, **fields) -> None:
    """Ajoute une ligne horodatée dans logs/whatsapp.log sans jamais écrire de token."""
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Filtrer par précaution tout champ pouvant contenir un token ou secret
        safe_fields = {}
        for k, v in fields.items():
            if any(
                secret_kw in k.lower()
                for secret_kw in ("token", "auth", "secret", "key")
            ):
                continue
            safe_fields[k] = v
        details = " ".join(
            f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in safe_fields.items()
        )
        with _log_path().open("a", encoding="utf-8") as fh:
            fh.write(f"[{ts}] {event} {details}\n")
    except Exception:  # le logging ne doit jamais bloquer l'envoi
        pass


class WhatsAppError(RuntimeError):
    """Classe d'erreur dédiée pour les échecs WhatsApp."""

    pass


@dataclass(frozen=True)
class SendResult:
    message_id: str
    status: str


class WhatsAppClient:
    """Client minimal pour l'API Meta WhatsApp Cloud."""

    def __init__(self, phone_number_id: str, access_token: str):
        if not phone_number_id or not access_token:
            raise WhatsAppError("Phone Number ID ou Token d'accès manquant.")
        self._phone_number_id = phone_number_id
        self._access_token = access_token
        self._base_url = BASE_URL
        self._headers = {"Authorization": f"Bearer {access_token}"}

    def upload_media(self, path: Path) -> str:
        """Upload un fichier sur l'endpoint média de Meta et renvoie le media_id."""
        if not path.exists():
            raise FileNotFoundError(f"Fichier introuvable pour upload : {path}")

        url = f"{self._base_url}/{self._phone_number_id}/media"
        content_type = (
            "application/pdf" if path.suffix.lower() == ".pdf" else "image/jpeg"
        )

        log_whatsapp(
            "UPLOAD_MEDIA_REQUEST",
            phone_number_id=self._phone_number_id,
            filename=path.name,
            content_type=content_type,
        )

        try:
            with path.open("rb") as fh:
                files = {"file": (path.name, fh, content_type)}
                data = {"messaging_product": "whatsapp", "type": content_type}
                resp = requests.post(
                    url, headers=self._headers, files=files, data=data, timeout=30
                )

            log_whatsapp(
                "UPLOAD_MEDIA_RESPONSE", http_status=resp.status_code, body=resp.text
            )

            if resp.status_code >= 400:
                raise WhatsAppError(f"HTTP {resp.status_code} - {resp.text}")

            res_json = resp.json()
            media_id = res_json.get("id")
            if not media_id:
                raise WhatsAppError(f"Pas d'ID média retourné par Meta : {res_json}")

            return str(media_id)

        except Exception as exc:
            if not isinstance(exc, WhatsAppError):
                raise WhatsAppError(f"Erreur lors de l'upload média : {exc}") from exc
            raise

    def send_document(
        self,
        to_e164: str,
        media_id: str,
        filename: str,
        template: str,
        lang: str,
        variables: list[str],
    ) -> SendResult:
        """Envoie un document via un modèle WhatsApp Meta approuvé."""
        url = f"{self._base_url}/{self._phone_number_id}/messages"

        # Structurer les paramètres
        # Variables corps de texte
        body_params = [{"type": "text", "text": val} for val in variables]

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_e164,
            "type": "template",
            "template": {
                "name": template,
                "language": {"code": lang},
                "components": [
                    {
                        "type": "header",
                        "parameters": [
                            {
                                "type": "document",
                                "document": {"id": media_id, "filename": filename},
                            }
                        ],
                    },
                    {"type": "body", "parameters": body_params},
                ],
            },
        }

        log_whatsapp(
            "SEND_MESSAGE_REQUEST",
            phone_number_id=self._phone_number_id,
            to=to_e164,
            template=template,
            lang=lang,
            media_id=media_id,
            filename=filename,
            variables=variables,
        )

        try:
            resp = requests.post(url, headers=self._headers, json=payload, timeout=30)
            log_whatsapp(
                "SEND_MESSAGE_RESPONSE", http_status=resp.status_code, body=resp.text
            )

            if resp.status_code >= 400:
                raise WhatsAppError(f"HTTP {resp.status_code} - {resp.text}")

            res_json = resp.json()
            messages = res_json.get("messages") or []
            if not messages:
                raise WhatsAppError(f"Réponse Meta sans message ID : {res_json}")

            message_id = messages[0].get("id")
            # Le statut retourné à l'envoi initial par Meta est généralement "accepted" ou "sent"
            status = messages[0].get("message_status", "sent")

            return SendResult(message_id=str(message_id), status=str(status))

        except Exception as exc:
            if not isinstance(exc, WhatsAppError):
                raise WhatsAppError(
                    f"Erreur lors de l'envoi du message : {exc}"
                ) from exc
            raise

    def get_status(self, message_id: str) -> str:
        """Interroge l'API Meta Graph pour obtenir le statut actuel du message."""
        url = f"{self._base_url}/{message_id}"

        log_whatsapp("GET_STATUS_REQUEST", message_id=message_id)

        try:
            resp = requests.get(url, headers=self._headers, timeout=30)
            log_whatsapp(
                "GET_STATUS_RESPONSE", http_status=resp.status_code, body=resp.text
            )

            if resp.status_code == 404:
                return "unknown"
            if resp.status_code >= 400:
                raise WhatsAppError(f"HTTP {resp.status_code} - {resp.text}")

            res_json = resp.json()
            # Dans l'API Graph WhatsApp, le statut peut être stocké dans 'status' ou être déduit.
            # Pour la résilience, on lit 'status' de l'objet ou on retourne 'sent'.
            return str(res_json.get("status", "sent"))

        except Exception as exc:
            if not isinstance(exc, WhatsAppError):
                raise WhatsAppError(
                    f"Erreur lors de la récupération du statut : {exc}"
                ) from exc
            raise
