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
class AIProviderCfg:
    """Un fournisseur IA et sa cle d'API propre (1 section [ai_provider_<name>])."""
    name: str
    api_key: str = ""
    base_url: str = ""
    model: str = ""


@dataclass(frozen=True)
class AIFeatureCfg:
    """Une fonctionnalite IA : quel provider, quel prompt (1 section [ai_feature_<name>])."""
    name: str
    provider: str
    prompt_path: str
    enabled: bool = True


@dataclass(frozen=True)
class AIConfig:
    """Configuration IA : fonctionnalites -> provider + prompt, decouplee du code."""
    providers: dict[str, AIProviderCfg]
    features: dict[str, AIFeatureCfg]

    def provider(self, name: str) -> "AIProviderCfg | None":
        return self.providers.get(name)

    def feature(self, name: str) -> "AIFeatureCfg | None":
        return self.features.get(name)


@dataclass(frozen=True)
class Config:
    paths: Paths
    mailjet: Mailjet
    mail: Mail
    ai: AIConfig


def app_dir() -> Path:
    """Dossier de l'application (a cote de l'exe une fois gele, sinon racine projet).

    Utilise pour resoudre les chemins relatifs (ex. prompts/ des fonctionnalites IA).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


# Alias retro-compatible (l'ancien nom prive reste utilise dans ce module).
_app_dir = app_dir


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

    # Sections IA OPTIONNELLES : [ai_provider_<name>] (cle d'API par provider) et
    # [ai_feature_<name>] (provider + prompt par fonctionnalite). Absentes => IA off.
    providers: dict[str, AIProviderCfg] = {}
    features: dict[str, AIFeatureCfg] = {}
    for section in parser.sections():
        if section.startswith("ai_provider_"):
            name = section[len("ai_provider_"):]
            providers[name] = AIProviderCfg(
                name=name,
                api_key=parser.get(section, "api_key", fallback=""),
                base_url=parser.get(section, "base_url", fallback=""),
                model=parser.get(section, "model", fallback=""),
            )
        elif section.startswith("ai_feature_"):
            name = section[len("ai_feature_"):]
            features[name] = AIFeatureCfg(
                name=name,
                provider=parser.get(section, "provider", fallback=""),
                prompt_path=parser.get(section, "prompt", fallback=""),
                enabled=parser.getboolean(section, "enabled", fallback=True),
            )
    ai = AIConfig(providers=providers, features=features)

    return Config(paths=paths, mailjet=mailjet, mail=mail, ai=ai)
