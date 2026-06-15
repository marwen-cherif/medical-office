from __future__ import annotations

import configparser
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    output: Path
    output_format: str = "jpg"


@dataclass(frozen=True)
class Mailjet:
    api_key: str
    api_secret: str
    from_email: str
    from_name: str
    sandbox: bool


@dataclass(frozen=True)
class Mail:
    template_id: int          # ID du template transactionnel Mailjet
    subject: str = ""         # optionnel : surcharge le sujet defini dans le template


@dataclass(frozen=True)
class Config:
    paths: Paths
    mailjet: Mailjet
    mail: Mail


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _resolve(base: Path, raw: str) -> Path:
    p = Path(raw)
    return p if p.is_absolute() else (base / p).resolve()


def load_config(config_path: Path | None = None) -> Config:
    base = _app_dir()
    cfg_path = config_path or (base / "config.ini")
    if not cfg_path.exists():
        raise FileNotFoundError(f"config.ini introuvable : {cfg_path}")

    parser = configparser.ConfigParser(interpolation=None)
    parser.read(cfg_path, encoding="utf-8")

    output_format = parser.get("paths", "output_format", fallback="jpg").strip().lower()
    if output_format not in ("jpg", "pdf"):
        raise ValueError(
            f"paths.output_format invalide : {output_format!r} (attendu 'jpg' ou 'pdf')."
        )
    paths = Paths(
        output=_resolve(base, parser.get("paths", "output", fallback="output")),
        output_format=output_format,
    )
    mailjet = Mailjet(
        api_key=parser.get("mailjet", "api_key"),
        api_secret=parser.get("mailjet", "api_secret"),
        from_email=parser.get("mailjet", "from_email"),
        from_name=parser.get("mailjet", "from_name"),
        sandbox=parser.getboolean("mailjet", "sandbox", fallback=False),
    )
    mail = Mail(
        template_id=parser.getint("mail", "template_id", fallback=0),
        subject=parser.get("mail", "subject", fallback=""),
    )
    return Config(paths=paths, mailjet=mailjet, mail=mail)
