"""Reglages d'impression par type de document (format papier + couleur).

Memorise, pour chaque type de document (= nom du modele : `facture`,
`demande_radio`, `examen_biologique`...), un format papier et un mode couleur
appliques silencieusement a l'impression. Stockage dans la table `meta` via
`repo.get_setting`/`set_setting` (comme `printer_name`) : **aucune migration de
schema**, additif et reversible.

Structure JSON memorisee sous la cle `print_settings` :

    { "<type>": { "paper": "A4"|"A5"|null, "color": "color"|"mono"|null }, ... }

Repli sur : cle absente / JSON invalide => dictionnaire vide ; valeurs inconnues
ignorees (=> None, soit « defaut imprimante »). Voir crm/printing.py pour
l'application au DEVMODE.
"""

from __future__ import annotations

import json
import sqlite3

from . import repo

# Cle `meta` unique contenant le JSON de tous les reglages par type.
PRINT_SETTINGS_KEY = "print_settings"

# Valeurs autorisees (toute autre valeur => None = « defaut imprimante »).
PAPERS = ("A4", "A5")
COLORS = ("color", "mono")


def _clean_paper(value) -> str | None:
    return value if value in PAPERS else None


def _clean_color(value) -> str | None:
    return value if value in COLORS else None


def all_settings(conn: sqlite3.Connection) -> dict[str, dict[str, str | None]]:
    """Tous les reglages memorises : `{ type: {"paper": ..., "color": ...} }`.

    Repli sur dictionnaire vide si la cle est absente ou le JSON invalide. Les
    valeurs inconnues sont normalisees a None (« defaut imprimante »).
    """
    raw = repo.get_setting(conn, PRINT_SETTINGS_KEY)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, dict[str, str | None]] = {}
    for doc_type, settings in data.items():
        if not isinstance(doc_type, str) or not isinstance(settings, dict):
            continue
        out[doc_type] = {
            "paper": _clean_paper(settings.get("paper")),
            "color": _clean_color(settings.get("color")),
        }
    return out


def get_settings_for(
    conn: sqlite3.Connection, doc_type: str
) -> dict[str, str | None]:
    """Reglage d'un type : `{"paper": ..., "color": ...}` (None si non defini)."""
    return all_settings(conn).get(doc_type, {"paper": None, "color": None})


def set_settings_for(
    conn: sqlite3.Connection,
    doc_type: str,
    paper: str | None,
    color: str | None,
) -> None:
    """Enregistre (ou met a jour) le reglage d'un type, en preservant les autres.

    `paper`/`color` a None (ou valeur inconnue) => « defaut imprimante » pour ce
    parametre. Si les deux sont None, l'entree du type est supprimee (repli total
    sur le defaut imprimante).
    """
    data = all_settings(conn)
    paper, color = _clean_paper(paper), _clean_color(color)
    if paper is None and color is None:
        data.pop(doc_type, None)
    else:
        data[doc_type] = {"paper": paper, "color": color}
    repo.set_setting(conn, PRINT_SETTINGS_KEY, json.dumps(data, ensure_ascii=False))
