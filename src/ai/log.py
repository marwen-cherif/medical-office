"""Journal des appels IA -> logs/ai.log (calque de src.mailer.log_mail).

Trace chaque tentative d'extraction : requete (URL, modele), statut HTTP, reponse
ou erreur. Ne leve jamais : le logging ne doit pas casser l'appelant.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


def _log_path() -> Path:
    base = (
        Path(sys.executable).parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent.parent.parent  # log.py -> ai -> src -> racine
    )
    log_dir = base / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "ai.log"


def log_ai(event: str, **fields) -> None:
    """Ajoute une ligne horodatee dans logs/ai.log (ne leve jamais d'erreur)."""
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        details = " ".join(
            f"{k}={json.dumps(v, ensure_ascii=False, default=str)}" for k, v in fields.items()
        )
        with _log_path().open("a", encoding="utf-8") as fh:
            fh.write(f"[{ts}] {event} {details}\n")
    except Exception:  # noqa: BLE001 -- le logging ne doit jamais casser l'extraction
        pass
