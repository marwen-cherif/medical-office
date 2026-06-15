"""Sauvegardes locales de la base SQLite.

Copie horodatee a chaque demarrage, avec purge pour ne garder que les plus
recentes. Aucune dependance externe (shutil de la stdlib).
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from .db import app_dir, default_db_path

KEEP = 10  # nombre de sauvegardes conservees


def backup_dir() -> Path:
    d = app_dir() / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def backup_db(db_path: Path | None = None) -> Path | None:
    """Copie la base vers backups/cabinet-AAAAMMJJ-HHMMSS.db puis purge les anciennes.

    Renvoie le chemin de la sauvegarde, ou None si la base n'existe pas encore
    (premier lancement). Best-effort : ne leve pas, la sauvegarde ne doit jamais
    empecher l'app de demarrer.
    """
    src = db_path or default_db_path()
    if not src.exists():
        return None
    try:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = backup_dir() / f"cabinet-{stamp}.db"
        shutil.copy2(src, dest)
        _prune()
        return dest
    except OSError:
        return None


def _prune() -> None:
    """Ne conserve que les KEEP sauvegardes les plus recentes."""
    backups = sorted(
        backup_dir().glob("cabinet-*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in backups[KEEP:]:
        try:
            old.unlink()
        except OSError:
            pass
