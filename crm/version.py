"""Version de l'application : version sémantique + tag de build.

- `__version__` : version sémantique, à incrémenter manuellement pour les releases.
- `build_tag()` : identifiant de build qui change à chaque build.
    * en build gelé (.exe) : lu dans `crm/_build_info.py`, généré par build-crm.bat
      (horodatage + hash git court) ;
    * en dev : dérivé de git (hash court), best-effort, sinon « dev ».

`crm/_build_info.py` est généré au build et git-ignoré ; son absence est normale en dev.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

__version__ = "1.0.0"


def _frozen() -> bool:
    return getattr(sys, "frozen", False)


def _build_info() -> dict:
    """Infos injectées au build (crm/_build_info.py), sinon {} (best-effort)."""
    try:
        from . import _build_info as bi  # type: ignore[attr-defined]
        return {"build": str(getattr(bi, "BUILD", "")),
                "commit": str(getattr(bi, "COMMIT", ""))}
    except Exception:  # noqa: BLE001 -- absence normale en dev
        return {}


def _git_short() -> str:
    """Hash git court (dev uniquement ; jamais en gelé, où git n'existe pas)."""
    if _frozen():
        return ""
    try:
        root = Path(__file__).resolve().parent.parent
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(root), capture_output=True, text=True, timeout=2,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:  # noqa: BLE001
        return ""


def build_tag() -> str:
    """Identifiant de build affiché (change à chaque build)."""
    if _frozen():
        build = _build_info().get("build")
        return build or "build"
    g = _git_short()
    return f"dev-{g}" if g else "dev"


def commit_tag() -> str:
    """Hash du commit (gelé : injecté au build ; dev : git), ou '' si inconnu."""
    return _build_info().get("commit", "") if _frozen() else _git_short()


def app_version() -> str:
    """Version courte, ex. « v1.0.0 »."""
    return f"v{__version__}"


def app_version_full() -> str:
    """Version complète pour le titre, ex. « v1.0.0 · 20260617-1432 »."""
    return f"v{__version__} · {build_tag()}"
