"""Entree image pour les providers vision : JPG/PNG direct, PDF rasterise (PyMuPDF).

Les factures sont des scans : JPG/PNG, ou PDF contenant une image. Pour un provider
vision, on envoie l'image telle quelle ; un PDF est rasterise (~200 DPI) en image(s).
Reutilise PyMuPDF (`fitz`), deja une dependance du projet (src/pdf_to_jpg.py).
"""

from __future__ import annotations

import base64
from pathlib import Path

from .base import AIError, ImagePart

_DPI_ZOOM = 200 / 72   # matrice de zoom PyMuPDF ~200 DPI (rendu lisible pour l'OCR)
_MAX_PAGES = 2         # le total figure quasi toujours en page 1 ou 2


def as_image_parts(path: Path, *, max_pages: int = _MAX_PAGES) -> list[ImagePart]:
    """Convertit un fichier (JPG/PNG ou PDF) en ImagePart(s). Leve AIError si non supporte."""
    suffix = path.suffix.lower()
    if suffix in (".jpg", ".jpeg", ".png"):
        media = "image/png" if suffix == ".png" else "image/jpeg"
        data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
        return [ImagePart(media_type=media, data_b64=data)]
    if suffix == ".pdf":
        import fitz  # PyMuPDF (cf. src/pdf_to_jpg.py)

        parts: list[ImagePart] = []
        matrix = fitz.Matrix(_DPI_ZOOM, _DPI_ZOOM)
        with fitz.open(path) as doc:
            for page in list(doc)[:max_pages]:
                pix = page.get_pixmap(matrix=matrix)
                data = base64.standard_b64encode(pix.tobytes("jpeg")).decode("ascii")
                parts.append(ImagePart(media_type="image/jpeg", data_b64=data))
        if not parts:
            raise AIError("PDF sans page exploitable.")
        return parts
    raise AIError(f"Format non supporte: {suffix}")
