"""Rendu serveur d'un schema dentaire anatomique (odontogramme) en image PNG.

La generation des notes d'honoraires est 100 % backend (Word COM, sans navigateur) :
pour imprimer un schema *anatomique* fidele a celui de l'ecran (react-odontogram),
on reutilise sa geometrie de dents (`src/odontogram_geometry.py`, MIT) et on compose
un SVG cote serveur, rasterise via PyMuPDF/`fitz` (deja embarque). Pas de dependance
navigateur ni a l'UI React.

Contrat : `render_png(dents)` recoit un ensemble de numeros FDI (chaines), met en
evidence les dents concernees, numerote chaque dent (FDI), et choisit la denture
automatiquement d'apres les numeros presents (adulte 11-48 / enfant 51-85 ; melange
=> les deux dentures empilees). Renvoie le chemin d'un PNG temporaire, ou None si
aucune dent FDI valide (l'appelant retire alors la balise <ODONTOGRAMME>).

Module volontairement independant de `crm/` (le moteur `src/` ne depend pas du CRM) :
le parsing FDI ici est un detail de rendu (placer/surligner une dent sur le schema),
pas la logique metier de la dette.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Iterable, Optional

from .odontogram_geometry import TEETH

# Couleurs (alignees sur la palette de l'app, cf. ui/src/index.css / OdontogrammeClinique).
_FILL_NEUTRE = "#eef2f9"
_OUTLINE_NEUTRE = "#9aa6bd"
_DETAIL_NEUTRE = "#c2cde0"
_FILL_CONCERNE = "#10357f"  # navy
_OUTLINE_CONCERNE = "#0a2052"
_DETAIL_CONCERNE = "#3f5da0"
_LABEL_NEUTRE = "#3b4658"   # numero FDI sur dent neutre
_LABEL_CONCERNE = "#ffffff"  # numero FDI sur dent concernee (sur fond navy)
_CAPTION = "#5b6678"

# Mise en page.
_GAP = 18.0          # espace vertical entre arcade haute et basse (unites viewBox)
_LABEL_FONT = 9.0    # numero FDI, place sur la dent
_MARGIN = 12.0       # marge autour du contenu
_CAPTION_FONT = 12.0
_CHART_GAP = 30.0    # espace entre les deux schemas (denture mixte)

# Quadrants FDI par coin du schema (denture permanente puis temporaire). Le schema
# standard place le quadrant maxillaire droit (1/5) en haut a gauche du lecteur.
#   coin -> (reflectX, reflectY, arch)
_CORNERS = {
    "UR": (False, False, "upper"),
    "UL": (True, False, "upper"),
    "LR": (False, True, "lower"),
    "LL": (True, True, "lower"),
}
# Chiffre de quadrant FDI par coin : permanentes (UR=1, UL=2, LR=4, LL=3) ; les
# temporaires derivent en +4 (UR=5, UL=6, LR=8, LL=7).
_QUAD_PERMANENT = {"UR": 1, "UL": 2, "LR": 4, "LL": 3}

_FDI_RE = re.compile(r"^([1-8])([1-8])$")


def parse_fdi(token: str) -> Optional[tuple[int, int]]:
    """`(quadrant, position)` d'un numero FDI valide, sinon None.

    Valide : permanentes 11-18/21-28/31-38/41-48 (position 1-8) et temporaires
    51-55/61-65/71-75/81-85 (position 1-5). Tout autre jeton est ignore pour le
    schema (sans bloquer : il reste dans le texte <DENTS>)."""
    m = _FDI_RE.match((token or "").strip())
    if not m:
        return None
    quad, pos = int(m.group(1)), int(m.group(2))
    if quad in (1, 2, 3, 4) and 1 <= pos <= 8:
        return quad, pos
    if quad in (5, 6, 7, 8) and 1 <= pos <= 5:
        return quad, pos
    return None


def _normalize(dents: Iterable[str]) -> set[str]:
    """Ensemble des jetons FDI valides parmi `dents` (decoupe tolerante)."""
    out: set[str] = set()
    for raw in dents:
        for tok in re.split(r"[,;\s]+", str(raw or "")):
            if parse_fdi(tok):
                out.add(tok.strip())
    return out


def _dentures(valides: set[str]) -> list[str]:
    """Dentures a dessiner d'apres les FDI presents : 'adulte' (quadrants 1-4) et/ou
    'enfant' (quadrants 5-8). Melange => les deux ; ordre adulte puis enfant."""
    out = []
    if any(parse_fdi(d)[0] in (1, 2, 3, 4) for d in valides):  # type: ignore[index]
        out.append("adulte")
    if any(parse_fdi(d)[0] in (5, 6, 7, 8) for d in valides):  # type: ignore[index]
        out.append("enfant")
    return out


# --- Composition d'un schema (une denture) ------------------------------------

def _denture_corners(denture: str) -> dict[str, int]:
    """Chiffre de quadrant FDI par coin pour une denture donnee."""
    if denture == "enfant":
        return {coin: q + 4 for coin, q in _QUAD_PERMANENT.items()}
    return dict(_QUAD_PERMANENT)


def _positions(denture: str) -> range:
    """Positions de dents par quadrant : 1-8 (adulte) ou 1-5 (enfant)."""
    return range(1, 6) if denture == "enfant" else range(1, 9)


class _Chart:
    """Schema d'une denture : SVG (groupe) + boite englobante, place a un offset y."""

    def __init__(self, denture: str, concerne: set[str]):
        self.denture = denture
        self.concerne = concerne
        teeth = [TEETH[p - 1] for p in _positions(denture)]
        bxs = [t["bbox"] for t in teeth]
        self.min_x = min(b[0] for b in bxs)
        self.min_y = min(b[1] for b in bxs)
        self.max_x = max(b[2] for b in bxs)
        self.max_y = max(b[3] for b in bxs)
        # Miroirs : axe vertical au bord incisif (max_x = ligne mediane), axe
        # horizontal sous l'arcade haute (max_y + GAP/2).
        self.mid_x = self.max_x
        self.y_line = self.max_y + _GAP / 2
        self.lower_max_y = 2 * self.y_line - self.min_y
        # Etendue du contenu (numeros poses sur les dents : bbox = celle des dents).
        self.content_min_x = self.min_x
        self.content_max_x = 2 * self.mid_x - self.min_x
        self.top_y = self.min_y
        self.bottom_y = self.lower_max_y
        self.width = (self.content_max_x - self.content_min_x)
        self.height = (self.bottom_y - self.top_y)

    def _tooth_center(self, tooth: dict, reflect_x: bool, reflect_y: bool) -> tuple[float, float]:
        """Centre global (repere du schema) d'une dent, pour poser son numero FDI."""
        cx, (b0, b1, b2, b3) = tooth["cx"], tooth["bbox"]
        cy = (b1 + b3) / 2
        gx = (2 * self.mid_x - cx) if reflect_x else cx
        gy = (2 * self.y_line - cy) if reflect_y else cy
        return gx, gy

    def _transform(self, reflect_x: bool, reflect_y: bool) -> str:
        if reflect_x and reflect_y:
            return f"translate({2 * self.mid_x},{2 * self.y_line}) scale(-1,-1)"
        if reflect_x:
            return f"translate({2 * self.mid_x},0) scale(-1,1)"
        if reflect_y:
            return f"translate(0,{2 * self.y_line}) scale(1,-1)"
        return ""

    def svg_group(self, y_offset: float) -> str:
        parts = [f'<g transform="translate(0,{y_offset})">']
        quad_of_coin = _denture_corners(self.denture)
        labels: list[str] = []
        for coin, (reflect_x, reflect_y, arch) in _CORNERS.items():
            quad = quad_of_coin[coin]
            tr = self._transform(reflect_x, reflect_y)
            parts.append(f'<g transform="{tr}">' if tr else "<g>")
            for pos in _positions(self.denture):
                tooth = TEETH[pos - 1]
                fdi = f"{quad}{pos}"
                on = fdi in self.concerne
                fill = _FILL_CONCERNE if on else _FILL_NEUTRE
                outline = _OUTLINE_CONCERNE if on else _OUTLINE_NEUTRE
                detail = _DETAIL_CONCERNE if on else _DETAIL_NEUTRE
                parts.append(f'<path d="{tooth["shadow"]}" fill="{fill}"/>')
                parts.append(
                    f'<path d="{tooth["outline"]}" fill="none" '
                    f'stroke="{outline}" stroke-width="1.4" '
                    'stroke-linejoin="round" stroke-linecap="round"/>'
                )
                for dline in tooth["detail"]:
                    parts.append(
                        f'<path d="{dline}" fill="none" stroke="{detail}" '
                        'stroke-width="0.8" stroke-linejoin="round" stroke-linecap="round"/>'
                    )
                # Numero FDI pose sur la dent (un par dent => aucun chevauchement) :
                # blanc sur une dent concernee (fond navy), fonce sinon.
                lx, ly = self._tooth_center(tooth, reflect_x, reflect_y)
                color = _LABEL_CONCERNE if on else _LABEL_NEUTRE
                labels.append(
                    f'<text x="{lx:.2f}" y="{ly:.2f}" font-size="{_LABEL_FONT}" '
                    f'font-family="DejaVu Sans, Arial, sans-serif" font-weight="700" '
                    f'fill="{color}" text-anchor="middle" '
                    'dominant-baseline="central">' + fdi + "</text>"
                )
            parts.append("</g>")
        parts.extend(labels)  # numeros par-dessus les dents
        parts.append("</g>")
        return "\n".join(parts)


def render_svg(dents: Iterable[str]) -> Optional[str]:
    """SVG du schema (une ou deux dentures), ou None si aucune dent FDI valide."""
    valides = _normalize(dents)
    if not valides:
        return None
    dentures = _dentures(valides)
    charts = [_Chart(d, valides) for d in dentures]

    captioned = len(charts) > 1
    cap_h = (_CAPTION_FONT + 6) if captioned else 0.0

    # Empilement vertical. Toutes les arcades partagent le meme repere x ; on cadre
    # sur l'union. y_offset translate chaque schema sous le precedent.
    content_min_x = min(c.content_min_x for c in charts)
    content_max_x = max(c.content_max_x for c in charts)

    groups: list[str] = []
    y_cursor = _MARGIN
    for c in charts:
        if captioned:
            label = "Denture permanente" if c.denture == "adulte" else "Denture temporaire"
            cx = (content_min_x + content_max_x) / 2
            groups.append(
                f'<text x="{cx:.2f}" y="{y_cursor + _CAPTION_FONT:.2f}" '
                f'font-size="{_CAPTION_FONT}" font-family="DejaVu Sans, Arial, sans-serif" '
                f'font-weight="600" fill="{_CAPTION}" text-anchor="middle">{label}</text>'
            )
            y_cursor += cap_h
        # Decale le schema pour que son sommet (top_y) tombe a y_cursor.
        groups.append(c.svg_group(y_cursor - c.top_y))
        y_cursor += c.height + _CHART_GAP

    total_w = (content_max_x - content_min_x) + 2 * _MARGIN
    total_h = (y_cursor - _CHART_GAP) + _MARGIN
    view_min_x = content_min_x - _MARGIN

    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{view_min_x:.2f} 0 {total_w:.2f} {total_h:.2f}" '
        f'width="{total_w:.0f}" height="{total_h:.0f}">'
    )
    bg = f'<rect x="{view_min_x:.2f}" y="0" width="{total_w:.2f}" height="{total_h:.2f}" fill="#ffffff"/>'
    return head + "\n" + bg + "\n" + "\n".join(groups) + "\n</svg>"


def render_png(dents: Iterable[str], out_path: Optional[Path] = None, *, zoom: float = 3.0) -> Optional[Path]:
    """Rasterise le schema en PNG. Renvoie le chemin (temporaire si `out_path` est
    None), ou None si aucune dent FDI valide (l'appelant retire la balise).

    `zoom` : facteur de rasterisation (nettete impression). Necessite PyMuPDF.
    """
    svg = render_svg(dents)
    if svg is None:
        return None
    import fitz

    if out_path is None:
        fd, name = tempfile.mkstemp(suffix=".png", prefix="odontogramme_")
        import os

        os.close(fd)
        out_path = Path(name)
    doc = fitz.open(stream=svg.encode("utf-8"), filetype="svg")
    try:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        pix.save(str(out_path))
    finally:
        doc.close()
    return out_path
