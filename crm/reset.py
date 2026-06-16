"""Remise a zero complete : vide la base et supprime les fichiers generes.

Comportement « nouvelle installation » :
- vide toutes les tables de data/cabinet.db et remet les compteurs a zero ;
- supprime les notes generees dans output/ (.jpg / .pdf), garde .gitkeep ;
- conserve les templates/ et config.ini.

On vide les tables (plutot que de supprimer le fichier) pour rester robuste
sous Windows si l'application CRM est ouverte au meme moment.

Au prochain lancement, l'app demarre sur une base vide (etat « neuf »).

Usage :
    python -m crm.reset            # demande une confirmation
    python -m crm.reset --yes      # sans confirmation (scripts)
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from .db import app_dir, connect, default_db_path

# Interface terminal coloree partagee (src/ui.py, style Claude).
try:
    from src import ui
except Exception:  # noqa: BLE001 - fallback si src indisponible
    ui = None  # type: ignore[assignment]


_GENERATED_SUFFIXES = {".jpg", ".jpeg", ".pdf", ".png"}


@dataclass
class ResetSummary:
    rows_deleted: int
    files_deleted: int
    logs_deleted: int


# Tables a vider (l'ordre respecte les cles etrangeres : enfants avant parents).
# meta n'est PAS videe : elle ne contient que schema_version, qui doit rester
# defini comme apres une installation neuve.
# L'ordre respecte les cles etrangeres :
# depense_reglements -> depenses -> factures -> prestataires.
_TABLES = (
    "job_items", "jobs", "paiements", "documents", "mail_templates", "patients",
    "depense_reglements", "depenses", "factures", "prestataires",
)


def _output_dir() -> Path:
    return app_dir() / "output"


def _logs_dir() -> Path:
    return app_dir() / "logs"


def perform_reset() -> ResetSummary:
    """Effectue la remise a zero. Ne demande aucune confirmation (a faire avant)."""
    # 1) Vide toutes les tables et remet les compteurs AUTOINCREMENT a zero.
    #    connect() recree le schema si besoin et reinsere meta.schema_version.
    rows_deleted = 0
    conn = connect()
    try:
        for table in _TABLES:
            rows_deleted += conn.execute(f"DELETE FROM {table}").rowcount
        # Reinitialise les compteurs d'id (sqlite_sequence absente si jamais cree).
        try:
            conn.execute(
                "DELETE FROM sqlite_sequence WHERE name IN (%s)"
                % ",".join("?" * len(_TABLES)),
                _TABLES,
            )
        except Exception:  # noqa: BLE001
            pass
        conn.commit()
        conn.execute("VACUUM")
    finally:
        conn.close()

    # 2) Supprime les notes generees dans output/ (garde .gitkeep et le reste).
    #    rglob : les documents sont desormais ranges dans des sous-dossiers
    #    d'archive par patient (output/<nom>_<prenom>_<naissance>/).
    files_deleted = 0
    out = _output_dir()
    if out.is_dir():
        for f in out.rglob("*"):
            if f.is_file() and f.suffix.lower() in _GENERATED_SUFFIXES:
                f.unlink()
                files_deleted += 1
        # Retire les dossiers d'archive devenus vides (en partant des plus profonds).
        for d in sorted((p for p in out.rglob("*") if p.is_dir()), reverse=True):
            try:
                d.rmdir()
            except OSError:
                pass  # pas vide (contient autre chose) : on le garde

    # 3) Vide les fichiers de log (.log) dans logs/.
    logs_deleted = 0
    logs = _logs_dir()
    if logs.is_dir():
        for f in logs.iterdir():
            if f.is_file() and f.suffix.lower() == ".log":
                f.unlink()
                logs_deleted += 1

    return ResetSummary(
        rows_deleted=rows_deleted, files_deleted=files_deleted, logs_deleted=logs_deleted
    )


def _confirm() -> bool:
    """Demande une confirmation explicite (taper SUPPRIMER)."""
    db_path = default_db_path()
    out = _output_dir()

    if ui is not None:
        ui.banner("Remise a zero", "Cette action est irreversible")
        ui.warn("Vont etre supprimes definitivement :")
        ui.note(f"- la base de donnees : {db_path}")
        ui.note(f"- les notes generees dans : {out}")
        ui.note(f"- les fichiers de log dans : {_logs_dir()}")
        ui.note("(templates/ et config.ini sont conserves)")
        print()
        try:
            answer = input(
                ui._c("  Tapez ", ui.DIM, ui.MUTED)
                + ui._c("SUPPRIMER", ui.BOLD, ui.RED)
                + ui._c(" pour confirmer : ", ui.DIM, ui.MUTED)
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
    else:
        print("ATTENTION : remise a zero irreversible.")
        print(f"- base de donnees : {db_path}")
        print(f"- notes generees dans : {out}")
        print(f"- fichiers de log dans : {_logs_dir()}")
        print("(templates/ et config.ini sont conserves)")
        try:
            answer = input("Tapez SUPPRIMER pour confirmer : ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return False

    return answer == "SUPPRIMER"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crm.reset",
        description="Vide la base et supprime les fichiers generes (remise a zero).",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Ne demande pas de confirmation (a utiliser dans un script).",
    )
    args = parser.parse_args(argv)

    if not args.yes and not _confirm():
        if ui is not None:
            ui.info("Annule : aucune donnee supprimee.")
        else:
            print("Annule : aucune donnee supprimee.")
        return 1

    summary = perform_reset()

    if ui is not None:
        print()
        ui.success("Remise a zero effectuee.")
        ui.stat("Lignes supprimees (base)", summary.rows_deleted, accent=ui.GREEN)
        ui.stat("Fichiers supprimes", summary.files_deleted, accent=ui.GREEN)
        ui.stat("Fichiers de log vides", summary.logs_deleted, accent=ui.GREEN)
        ui.note("Au prochain lancement, l'app demarre sur une base vide.")
    else:
        print("Remise a zero effectuee.")
        print(f"  Lignes supprimees (base) : {summary.rows_deleted}")
        print(f"  Fichiers supprimes : {summary.files_deleted}")
        print(f"  Fichiers de log vides : {summary.logs_deleted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
