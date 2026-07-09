from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF


def pdf_first_page_to_jpg(pdf_path: Path, jpg_path: Path, dpi: int = 200) -> Path:
    """Rend la première page du PDF en JPG à la résolution demandée."""
    jpg_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    try:
        if doc.page_count == 0:
            raise ValueError(f"PDF vide : {pdf_path}")
        page = doc.load_page(0)
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        pix.save(str(jpg_path), jpg_quality=92)
    finally:
        doc.close()
    return jpg_path
