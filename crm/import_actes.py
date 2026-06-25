"""Import en masse du referentiel d'actes depuis un fichier Excel.

Alimente la table `actes` (referentiel tarife, cf. crm/db.py v9) a partir d'un
classeur .xlsx contenant des triplets (libelle, prix/montant, code).

Idempotent : relancer le meme fichier MET A JOUR les actes existants au lieu de
creer des doublons. Cle de rapprochement (pour reconnaitre un acte deja present) :

  1. le CODE s'il est renseigne (cle stable, ex. nomenclature) ;
  2. sinon le LIBELLE (insensible aux accents et a la casse, comme dans l'app).

Format attendu du classeur (premiere feuille par defaut) :

  - AVEC une ligne d'entete : les colonnes sont reconnues par leur nom
    (« libelle / acte / designation », « prix / montant / tarif », « code / reference »),
    quel que soit leur ordre. Une colonne « code » est facultative.
  - SANS entete : colonnes par position -> 1 = libelle, 2 = prix, 3 = code.

Les montants acceptent le format francais (« 1 800,00 », « 1800.00 », « 120 € »...).

Usage :
    python -m crm.import_actes actes.xlsx
    python -m crm.import_actes actes.xlsx --feuille "Tarifs"
    python -m crm.import_actes actes.xlsx --dry-run     # simulation, n'ecrit rien
    python -m crm.import_actes --modele modele_actes.xlsx   # genere un fichier exemple

Une sauvegarde de la base est prise avant tout ecriture (cf. crm/backup.py).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import repo
from .backup import backup_db
from .db import connect, default_db_path
from .repo import slugify

# Interface terminal coloree partagee (src/ui.py), comme crm/reset.py.
try:
    from src import ui
except Exception:  # noqa: BLE001 - fallback si src indisponible
    ui = None  # type: ignore[assignment]


# Mots-cles d'entete reconnus (compares au slug de la cellule d'entete).
_LIBELLE_KEYS = {
    "libelle", "libelles", "label", "acte", "actes", "designation",
    "intitule", "nom", "prestation", "description",
}
_PRIX_KEYS = {
    "prix", "montant", "montants", "tarif", "tarifs", "cout", "couts",
    "price", "amount", "honoraire", "honoraires",
}
_CODE_KEYS = {
    "code", "codes", "reference", "ref", "nomenclature", "ngap", "ccam",
}


@dataclass
class ImportSummary:
    created: int = 0
    updated: int = 0
    skipped: int = 0          # lignes vides ignorees
    errors: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


# --- Lecture / normalisation des cellules --------------------------------------

def _parse_montant(value: object) -> Optional[float]:
    """Convertit une cellule en nombre, en tolerant le format francais.

    Renvoie None si la cellule est vide. Leve ValueError si le contenu n'est pas
    interpretable comme un montant.
    """
    if value is None:
        return None
    if isinstance(value, bool):  # bool est un int en Python : on refuse
        raise ValueError("valeur booleenne")
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    # Retire espaces (y compris insecables) et tout sauf chiffres , . -
    s = s.replace(" ", "").replace("\xa0", "").replace(" ", "")
    s = re.sub(r"[^0-9,.\-]", "", s)
    if not s or s in {"-", ".", ","}:
        raise ValueError(f"montant illisible : {value!r}")
    # Si , et . coexistent, le dernier separateur est le decimal.
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError as exc:
        raise ValueError(f"montant illisible : {value!r}") from exc


def _clean_libelle(value: object) -> str:
    return "" if value is None else str(value).strip()


def _parse_code(value: object) -> Optional[str]:
    """Code en texte. Un code numerique entier (123.0) devient « 123 »."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    s = str(value).strip()
    return s or None


def _detect_columns(header: tuple) -> Optional[dict[str, Optional[int]]]:
    """Detecte les colonnes a partir d'une ligne d'entete.

    Renvoie {'libelle': i, 'prix': j, 'code': k|None} si l'entete contient au
    moins une colonne libelle OU prix reconnue, sinon None (pas d'entete -> mode
    positionnel).
    """
    cols: dict[str, Optional[int]] = {"libelle": None, "prix": None, "code": None}
    for i, cell in enumerate(header):
        slug = slugify(str(cell)) if cell is not None else ""
        if not slug:
            continue
        if cols["libelle"] is None and slug in _LIBELLE_KEYS:
            cols["libelle"] = i
        elif cols["prix"] is None and slug in _PRIX_KEYS:
            cols["prix"] = i
        elif cols["code"] is None and slug in _CODE_KEYS:
            cols["code"] = i
    if cols["libelle"] is None and cols["prix"] is None:
        return None  # aucune entete reconnue
    # Valeurs par defaut pour une colonne manquante (rare : entete partielle).
    if cols["libelle"] is None:
        cols["libelle"] = 0
    if cols["prix"] is None:
        cols["prix"] = 1
    return cols


def _read_rows(path: Path, feuille: Optional[str]) -> list[tuple[int, str, object, object]]:
    """Lit le classeur et renvoie [(no_ligne, libelle, valeur_prix, valeur_code)].

    Le no_ligne (1-based, tel qu'affiche dans Excel) sert aux messages d'erreur.
    """
    try:
        import openpyxl  # import tardif : dependance optionnelle
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Le module 'openpyxl' est requis pour lire un .xlsx "
            "(pip install openpyxl)."
        ) from exc

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        if feuille:
            if feuille not in wb.sheetnames:
                raise RuntimeError(
                    f"Feuille « {feuille} » introuvable. "
                    f"Feuilles disponibles : {', '.join(wb.sheetnames)}"
                )
            ws = wb[feuille]
        else:
            ws = wb.active

        all_rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()

    if not all_rows:
        return []

    cols = _detect_columns(all_rows[0])
    if cols is not None:
        data_rows = all_rows[1:]
        start_line = 2  # la ligne 1 est l'entete
        i_lib, i_prix, i_code = cols["libelle"], cols["prix"], cols["code"]
    else:
        data_rows = all_rows
        start_line = 1
        i_lib, i_prix, i_code = 0, 1, 2  # positionnel

    out: list[tuple[int, str, object, object]] = []
    for offset, row in enumerate(data_rows):
        line_no = start_line + offset

        def _at(idx: Optional[int]):
            if idx is None or idx >= len(row):
                return None
            return row[idx]

        libelle = _clean_libelle(_at(i_lib))
        out.append((line_no, libelle, _at(i_prix), _at(i_code)))
    return out


# --- Rapprochement avec un acte existant ---------------------------------------

def _find_existing(conn, code: Optional[str], libelle: str) -> Optional[repo.Acte]:
    """Acte deja present correspondant a la ligne, ou None.

    Priorite au code (cle stable, actifs ET inactifs) ; a defaut, le libelle
    parmi les actes actifs (reutilise la regle de doublon de l'application).
    """
    if code:
        row = conn.execute(
            "SELECT id FROM actes WHERE code = ? ORDER BY id LIMIT 1", (code,)
        ).fetchone()
        if row:
            return repo.get_acte(conn, row["id"])
    return repo.find_acte_by_libelle(conn, libelle)


# --- Import --------------------------------------------------------------------

def import_actes(path: Path, feuille: Optional[str] = None, dry_run: bool = False) -> ImportSummary:
    """Importe les actes du classeur. N'ecrit rien si dry_run=True."""
    rows = _read_rows(path, feuille)
    summary = ImportSummary()

    conn = connect()
    try:
        for line_no, libelle, raw_prix, raw_code in rows:
            if not libelle and raw_prix is None and raw_code is None:
                summary.skipped += 1  # ligne entierement vide
                continue
            if not libelle:
                summary.errors.append(f"Ligne {line_no} : libelle manquant, ignoree.")
                summary.skipped += 1
                continue
            try:
                prix = _parse_montant(raw_prix)
            except ValueError as exc:
                summary.errors.append(f"Ligne {line_no} ({libelle}) : {exc}, ignoree.")
                summary.skipped += 1
                continue
            if prix is None:
                prix = 0.0  # libelle sans prix -> acte a 0 (ex. controle)
            if prix < 0:
                summary.errors.append(
                    f"Ligne {line_no} ({libelle}) : prix negatif, ignoree."
                )
                summary.skipped += 1
                continue

            code = _parse_code(raw_code)
            existing = _find_existing(conn, code, libelle)

            if existing is not None:
                existing.libelle = libelle
                existing.prix = prix
                existing.code = code or existing.code
                if not dry_run:
                    repo.update_acte(conn, existing)
                summary.updated += 1
            else:
                if not dry_run:
                    repo.create_acte(
                        conn, repo.Acte(id=None, libelle=libelle, prix=prix, code=code)
                    )
                summary.created += 1
    finally:
        conn.close()

    return summary


# --- Generation d'un modele Excel ----------------------------------------------

def write_template(path: Path) -> None:
    """Ecrit un classeur VIDE a remplir : seulement la ligne d'entete (en gras),
    colonnes elargies. Libelle obligatoire ; Prix au format francais accepte
    (« 1 800,00 ») ; Code facultatif."""
    import openpyxl
    from openpyxl.styles import Font

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Actes"
    ws.append(["Libelle", "Prix", "Code"])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.column_dimensions["A"].width = 36  # Libelle
    ws.column_dimensions["B"].width = 14  # Prix
    ws.column_dimensions["C"].width = 14  # Code
    ws.freeze_panes = "A2"  # garde l'entete visible au defilement
    wb.save(path)


# --- CLI -----------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crm.import_actes",
        description="Importe le referentiel d'actes (libelle, prix, code) depuis un .xlsx.",
    )
    parser.add_argument("fichier", nargs="?", help="Classeur .xlsx a importer.")
    parser.add_argument("--feuille", help="Nom de la feuille (defaut : la premiere).")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simulation : affiche ce qui serait fait sans rien ecrire en base.",
    )
    parser.add_argument(
        "--modele", metavar="FICHIER.xlsx",
        help="Genere un fichier modele vierge a remplir, puis quitte.",
    )
    args = parser.parse_args(argv)

    def _say(level: str, text: str) -> None:
        fn = getattr(ui, level, None) if ui is not None else None
        if fn is not None:
            fn(text)
        else:
            print(text)

    # Mode generation de modele.
    if args.modele:
        try:
            write_template(Path(args.modele))
        except Exception as exc:  # noqa: BLE001
            _say("error", f"Echec de generation du modele : {exc}")
            return 1
        _say("success", f"Modele cree : {args.modele}")
        return 0

    if not args.fichier:
        parser.error("indiquez un fichier .xlsx (ou utilisez --modele pour un exemple).")

    path = Path(args.fichier)
    if not path.is_file():
        _say("error", f"Fichier introuvable : {path}")
        return 1

    if ui is not None:
        ui.banner("Import du referentiel d'actes", str(path))

    # Sauvegarde avant ecriture (jamais en simulation).
    if not args.dry_run:
        dest = backup_db()
        if dest is not None:
            _say("note", f"Sauvegarde prealable : {dest}")
        elif not default_db_path().exists():
            _say("note", "Base inexistante : elle sera creee.")

    try:
        summary = import_actes(path, feuille=args.feuille, dry_run=args.dry_run)
    except RuntimeError as exc:
        _say("error", str(exc))
        return 1

    if args.dry_run:
        _say("warn", "SIMULATION : aucune modification ecrite en base.")

    if summary.errors:
        if ui is not None:
            ui.section("Lignes ignorees")
        for msg in summary.errors:
            _say("warn", msg)

    if ui is not None:
        print()
        ui.success("Import termine." if not args.dry_run else "Simulation terminee.")
        ui.stat("Actes crees", summary.created, accent=ui.GREEN)
        ui.stat("Actes mis a jour", summary.updated, accent=ui.GREEN)
        ui.stat("Lignes ignorees", summary.skipped,
                accent=ui.YELLOW if summary.skipped else "")
    else:
        print("Import termine." if not args.dry_run else "Simulation terminee.")
        print(f"  Actes crees : {summary.created}")
        print(f"  Actes mis a jour : {summary.updated}")
        print(f"  Lignes ignorees : {summary.skipped}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
