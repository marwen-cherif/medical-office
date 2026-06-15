from __future__ import annotations

import base64
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests

from .config import Mail, Mailjet

SEND_URL = "https://api.mailjet.com/v3.1/send"
MESSAGE_URL = "https://api.mailjet.com/v3/REST/message/{message_id}"
HISTORY_URL = "https://api.mailjet.com/v3/REST/messagehistory/{message_id}"


def _log_path() -> Path:
    base = (
        Path(sys.executable).parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent.parent
    )
    log_dir = base / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "mailjet.log"


def log_mail(event: str, **fields) -> None:
    """Ajoute une ligne horodatee dans logs/mailjet.log (ne leve jamais d'erreur)."""
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        details = " ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in fields.items())
        with _log_path().open("a", encoding="utf-8") as fh:
            fh.write(f"[{ts}] {event} {details}\n")
    except Exception:  # noqa: BLE001 -- le logging ne doit jamais casser l'envoi
        pass


@dataclass(frozen=True)
class SendResult:
    message_id: str
    status: str  # statut renvoye par Mailjet a l'envoi (ex: "success")


class MailjetError(RuntimeError):
    pass


class MailjetClient:
    """Client minimal pour Mailjet Send API v3.1 + lookup statut."""

    def __init__(self, mailjet_cfg: Mailjet, mail_cfg: Mail):
        self._cfg = mailjet_cfg
        self._mail = mail_cfg
        self._auth = (mailjet_cfg.api_key, mailjet_cfg.api_secret)

    def send(
        self,
        to_email: str,
        attachment: Path,
        custom_id: str | None = None,
        variables: dict | None = None,
        template_id: int | None = None,
    ) -> SendResult:
        template_id = template_id or self._mail.template_id
        if not template_id:
            raise MailjetError(
                "Aucun template Mailjet selectionne : choisissez un modele d'email "
                "(ou renseignez 'template_id' dans config.ini pour le CLI)."
            )
        b64 = base64.b64encode(attachment.read_bytes()).decode("ascii")
        content_type = (
            "application/pdf"
            if attachment.suffix.lower() == ".pdf"
            else "image/jpeg"
        )
        message: dict = {
            "From": {"Email": self._cfg.from_email, "Name": self._cfg.from_name},
            "To": [{"Email": to_email}],
            "TemplateID": template_id,
            "TemplateLanguage": True,
            "Attachments": [
                {
                    "ContentType": content_type,
                    "Filename": attachment.name,
                    "Base64Content": b64,
                }
            ],
            "TrackOpens": "enabled",
            "TrackClicks": "enabled",
        }
        if self._mail.subject:
            message["Subject"] = self._mail.subject  # surcharge optionnelle
        if variables:
            message["Variables"] = variables
        if custom_id:
            message["CustomID"] = custom_id

        payload: dict = {"Messages": [message]}
        if self._cfg.sandbox:
            payload["SandboxMode"] = True

        log_mail(
            "SEND_REQUEST",
            to=to_email,
            from_email=self._cfg.from_email,
            template_id=template_id,
            sandbox=self._cfg.sandbox,
            custom_id=custom_id,
            attachment=attachment.name,
        )

        resp = requests.post(SEND_URL, auth=self._auth, json=payload, timeout=30)
        # corps brut renvoye par Mailjet : la cle pour comprendre un envoi "fantome"
        log_mail("SEND_RESPONSE", http_status=resp.status_code, body=resp.text)

        if resp.status_code >= 400:
            raise MailjetError(f"HTTP {resp.status_code} - {resp.text}")
        data = resp.json()

        messages = data.get("Messages") or []
        if not messages:
            raise MailjetError(f"Reponse Mailjet sans 'Messages' : {data}")
        m = messages[0]
        status = m.get("Status", "")
        if status != "success":
            errors = m.get("Errors") or []
            log_mail("SEND_FAILED", to=to_email, status=status, errors=errors)
            raise MailjetError(f"Statut Mailjet '{status}' : {errors}")

        to_list = m.get("To") or []
        message_id = str(to_list[0].get("MessageID", "")) if to_list else ""
        if not message_id or message_id == "0":
            # Mailjet a repondu "success" mais sans vrai MessageID : le mail
            # n'est pas reellement parti (domaine non authentifie, etc.).
            log_mail("SEND_NO_MESSAGE_ID", to=to_email, status=status, message=m)
            raise MailjetError(
                f"Mailjet a renvoye 'success' sans MessageID valide (message_id={message_id!r}). "
                f"Le mail n'a pas ete reellement envoye. Reponse : {m}"
            )
        log_mail("SEND_OK", to=to_email, message_id=message_id, status=status)
        return SendResult(message_id=message_id, status=status)

    def fetch_message_status(self, message_id: str) -> str:
        """Recupere le statut courant d'un message envoye (sent, opened, clicked, bounce...)."""
        url = MESSAGE_URL.format(message_id=message_id)
        resp = requests.get(url, auth=self._auth, timeout=30)
        if resp.status_code == 404:
            return "unknown"
        if resp.status_code >= 400:
            raise MailjetError(f"HTTP {resp.status_code} - {resp.text}")
        data = resp.json()
        items = data.get("Data") or []
        if not items:
            return "unknown"
        return str(items[0].get("Status", "unknown"))

    def fetch_message_history(self, message_id: str) -> list[dict]:
        """Chronologie des evenements d'un message (ouvert, clic...) horodates.

        Renvoie la liste brute `Data` de /messagehistory (chaque entree a un champ
        `EventAt` en timestamp Unix et un champ d'etat `State`/`EventType`), ou []
        si indisponible (404). Sert au suivi detaille des ouvertures/clics.
        """
        url = HISTORY_URL.format(message_id=message_id)
        resp = requests.get(url, auth=self._auth, timeout=30)
        if resp.status_code == 404:
            return []
        if resp.status_code >= 400:
            raise MailjetError(f"HTTP {resp.status_code} - {resp.text}")
        return resp.json().get("Data") or []
