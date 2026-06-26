"""Extrait la geometrie anatomique des dents depuis le bundle `react-odontogram`
(MIT, ui/node_modules) et genere `src/odontogram_geometry.py` (module de donnees
committe, embarque dans l'.exe).

Pourquoi : la generation des notes d'honoraires est 100 % backend Python (sans
navigateur). Pour imprimer un schema dentaire *anatomique* fidele a celui affiche
a l'ecran (react-odontogram), on reutilise la meme geometrie de dents — silhouettes
SVG (`outlinePath`), corps (`shadowPath`), details (`lineHighlightPath`) — et la
disposition par quadrant (transforms `l1`, layout « square »). On l'extrait une fois
au dev et on committe le module genere ; node_modules n'est pas embarque dans l'.exe.

Usage :
    python -m tools.extract_odontogram_geometry        # ecrit src/odontogram_geometry.py

Source : ui/node_modules/react-odontogram/dist/index.js (version installee).
Licence react-odontogram : MIT (Pratik Sharma) — attribution conservee dans le
module genere.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "ui" / "node_modules" / "react-odontogram" / "dist" / "index.js"
OUT = ROOT / "src" / "odontogram_geometry.py"

# Layout « square » : 4 quadrants, leur transform SVG et le chiffre de quadrant FDI
# (l1 du bundle). Ordre des entrees : Upper Right, Upper Left, Lower Right, Lower Left.
# Mapping vers les quadrants FDI : UR=1, UL=2, LR=4, LL=3 (permanentes) ; pour la
# denture temporaire on derive UR=5, UL=6, LR=8, LL=7 (chiffre +4).
_FDI_PERMANENT = [1, 2, 4, 3]
_ARCHES = ["upper", "upper", "lower", "lower"]


def _read_bundle() -> str:
    if not BUNDLE.exists():
        raise SystemExit(
            f"Bundle introuvable : {BUNDLE}\n"
            "Installer les deps UI (npm install dans ui/) avant l'extraction."
        )
    return BUNDLE.read_text(encoding="utf-8", errors="replace")


def _balanced_end(text: str, start: int, open_ch: str, close_ch: str) -> int:
    """Index (exclus) de la fermeture equilibree de `text[start]==open_ch`, en
    respectant les chaines entre guillemets (les chemins SVG contiennent des
    crochets/accolades improbables, mais les valeurs de chaine sont ignorees)."""
    depth = 0
    i = start
    instr = False
    while i < len(text):
        c = text[i]
        if instr:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                instr = False
        elif c == '"':
            instr = True
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise SystemExit(f"Bloc {open_ch}{close_ch} non equilibre a partir de {start}.")


def _extract_teeth(s: str) -> list[dict]:
    """Les 8 silhouettes permanentes (r1) : name(1..8), type, et les 3 chemins.

    `r1` est borne par comptage d'accolades (certaines valeurs voisines dans le
    bundle sont des tableaux : un simple `}]` couperait l'array trop tot). Chaque
    objet-dent porte des champs *chaine* (les chemins SVG ne contiennent jamais de
    guillemet)."""
    start = s.find("r1=[")
    if start < 0:
        raise SystemExit("Tableau r1 (geometrie square) introuvable.")
    arr_start = s.index("[", start)
    arr_end = _balanced_end(s, arr_start, "[", "]")
    r1 = s[arr_start:arr_end]

    objs: list[str] = []
    j = 0
    while True:
        b = r1.find("{", j)
        if b < 0:
            break
        e = _balanced_end(r1, b, "{", "}")
        objs.append(r1[b:e])
        j = e
    if len(objs) != 8:
        raise SystemExit(f"r1 : {len(objs)} dents (8 attendues).")

    teeth = []
    for obj in objs:
        def field(key: str) -> str:
            m = re.search(re.escape(key) + r':"([^"]*)"', obj)
            if not m:
                raise SystemExit(f"Champ {key} absent d'une dent r1.")
            return m.group(1)

        def paths(key: str) -> list[str]:
            """Valeur d'un champ chemin pouvant etre une chaine OU un tableau de
            chaines (certaines molaires ont plusieurs lignes de detail)."""
            m = re.search(re.escape(key) + r":", obj)
            if not m:
                return []
            p = m.end()
            if obj[p] == '"':
                mm = re.match(r'"([^"]*)"', obj[p:])
                return [mm.group(1)] if mm else []
            if obj[p] == "[":
                end = _balanced_end(obj, p, "[", "]")
                return re.findall(r'"([^"]*)"', obj[p:end])
            return []

        teeth.append(
            {
                "pos": int(field("name")),
                "type": field("type"),
                "outline": field("outlinePath"),
                "shadow": field("shadowPath"),
                "detail": paths("lineHighlightPath"),
            }
        )
    teeth.sort(key=lambda t: t["pos"])
    return teeth


def _extract_quadrant_transforms(s: str) -> list[str]:
    """Les 4 transforms du layout « square » (l1)."""
    m = re.search(r'l1=(\[\{name:"first",transform:.*?\}\])', s)
    if not m:
        raise SystemExit("Layout l1 (square) introuvable dans le bundle.")
    transforms = re.findall(r'transform:"([^"]*)"', m.group(1))
    if len(transforms) != 4:
        raise SystemExit(f"l1 : {len(transforms)} transforms (4 attendus).")
    return transforms


def _extract_viewbox(s: str) -> tuple[float, float, float, float]:
    """viewBox plein du layout « square » : p1('square') -> '0 0 900 150'."""
    m = re.search(r'if\(t==="square"\)return[^;]*?:"([0-9 .]+)"', s)
    # p1 renvoie pour square : upper "0 0 900 75", lower "0 75 900 75 ", full "0 0 900 150".
    # On veut le plein (branche sans e) : cherche '0 0 900 150'.
    full = re.search(r'"(0 0 900 150)"', s)
    if not full:
        raise SystemExit("viewBox square plein (0 0 900 150) introuvable.")
    return tuple(float(x) for x in full.group(1).split())  # type: ignore[return-value]


# --- Parsing minimal de chemin SVG pour bbox (centrage des numeros FDI) --------

_TOKEN_RE = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|-?\d*\.?\d+(?:e-?\d+)?")


def _path_bbox(d: str) -> tuple[float, float, float, float]:
    """Boite englobante approchee d'un chemin SVG (points d'ancrage, suffit au
    centrage d'un libelle). Suit le point courant a travers les commandes ; pour les
    courbes seul le point final deplace le curseur (les points de controle sont
    ignores : bbox legerement reduite, sans impact sur le centre)."""
    tokens = _TOKEN_RE.findall(d)
    i = 0
    cx = cy = 0.0
    start_x = start_y = 0.0
    cmd = ""
    xs: list[float] = []
    ys: list[float] = []

    def num() -> float:
        nonlocal i
        v = float(tokens[i])
        i += 1
        return v

    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if re.match(r"[A-Za-z]", tok):
            cmd = tok
            i += 1
            if cmd in "Zz":
                cx, cy = start_x, start_y
                continue
        rel = cmd.islower()
        c = cmd.upper()
        if c == "M":
            x = num(); y = num()
            cx = (cx + x) if rel else x
            cy = (cy + y) if rel else y
            start_x, start_y = cx, cy
            cmd = "l" if cmd == "m" else "L"  # M suivi de coords implicites = L
        elif c == "L":
            x = num(); y = num()
            cx = (cx + x) if rel else x
            cy = (cy + y) if rel else y
        elif c == "H":
            x = num()
            cx = (cx + x) if rel else x
        elif c == "V":
            y = num()
            cy = (cy + y) if rel else y
        elif c == "C":
            num(); num(); num(); num()
            x = num(); y = num()
            cx = (cx + x) if rel else x
            cy = (cy + y) if rel else y
        elif c in ("S", "Q"):
            num(); num()
            x = num(); y = num()
            cx = (cx + x) if rel else x
            cy = (cy + y) if rel else y
        elif c == "T":
            x = num(); y = num()
            cx = (cx + x) if rel else x
            cy = (cy + y) if rel else y
        elif c == "A":
            num(); num(); num(); num(); num()
            x = num(); y = num()
            cx = (cx + x) if rel else x
            cy = (cy + y) if rel else y
        else:
            i += 1
            continue
        xs.append(cx)
        ys.append(cy)
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs), min(ys), max(xs), max(ys))


def _render_module(teeth: list[dict], transforms: list[str], viewbox) -> str:
    quad_lines = []
    for idx, (tr, fdi, arch) in enumerate(zip(transforms, _FDI_PERMANENT, _ARCHES)):
        quad_lines.append(
            f"    {{'transform': {tr!r}, 'fdi': {fdi}, 'arch': {arch!r}}},"
        )
    teeth_lines = []
    for t in teeth:
        bb = _path_bbox(t["outline"])
        cx = (bb[0] + bb[2]) / 2
        teeth_lines.append(
            "    {\n"
            f"        'pos': {t['pos']}, 'type': {t['type']!r},\n"
            f"        'cx': {cx:.3f}, 'bbox': ({bb[0]:.3f}, {bb[1]:.3f}, {bb[2]:.3f}, {bb[3]:.3f}),\n"
            f"        'outline': {t['outline']!r},\n"
            f"        'shadow': {t['shadow']!r},\n"
            f"        'detail': {t['detail']!r},\n"
            "    },"
        )
    return (
        '"""Geometrie anatomique des dents (GENERE — ne pas editer a la main).\n\n'
        "Genere par `tools/extract_odontogram_geometry.py` depuis react-odontogram\n"
        "(MIT, Pratik Sharma). Reutilise pour rendre le schema dentaire des notes\n"
        "d'honoraires cote serveur (cf. src/odontogram_render.py).\n\n"
        "Layout « square » : viewBox plein, 4 quadrants (transform SVG + chiffre FDI),\n"
        "8 silhouettes permanentes (position 1=incisive centrale .. 8=3e molaire) avec\n"
        "outline (contour), shadow (corps, colore quand concerne) et detail (lignes).\n"
        '"""\n\n'
        "from __future__ import annotations\n\n"
        f"VIEWBOX = {tuple(viewbox)!r}  # (min_x, min_y, width, height)\n\n"
        "# Quadrants (ordre l1) : UR, UL, LR, LL. 'fdi' = chiffre de quadrant permanent\n"
        "# (temporaire = +4). 'arch' situe l'arcade pour le placement des numeros.\n"
        "QUADRANTS = [\n" + "\n".join(quad_lines) + "\n]\n\n"
        "# Silhouettes d'un quadrant (deja disposees en rangee) ; 'cx' = centre x local\n"
        "# (centrage du numero FDI), 'bbox' = (min_x, min_y, max_x, max_y).\n"
        "TEETH = [\n" + "\n".join(teeth_lines) + "\n]\n"
    )


def main() -> None:
    s = _read_bundle()
    teeth = _extract_teeth(s)
    transforms = _extract_quadrant_transforms(s)
    viewbox = _extract_viewbox(s)
    OUT.write_text(_render_module(teeth, transforms, viewbox), encoding="utf-8")
    print(f"OK : {OUT.relative_to(ROOT)} ({len(teeth)} dents, {len(transforms)} quadrants)")
    print("Centres x (positions 1..8) :", [round(t["cx"], 1) for t in teeth] if False else
          [round((_path_bbox(t["outline"])[0] + _path_bbox(t["outline"])[2]) / 2, 1) for t in teeth])


if __name__ == "__main__":
    main()
