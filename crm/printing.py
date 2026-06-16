"""Impression directe des documents generes vers une imprimante Windows.

Approche « directe » : on pilote l'imprimante via GDI avec pywin32 (deja embarque
pour piloter Word). L'imprimante cible est choisie une fois dans Parametrage et
memorisee dans la table `meta` (cf. repo.get_setting/set_setting) ; ce module se
contente de lister les imprimantes et d'envoyer un fichier (JPG ou PDF) a
l'imprimante nommee, silencieusement (sans boite de dialogue systeme).

Windows uniquement, comme la generation Word. En mode web (crm_web.py),
l'impression s'execute cote serveur : elle part donc de l'ordinateur ou tourne
l'application, vers son imprimante reseau — et non depuis le navigateur client.

Les notes d'honoraires tiennent sur une page ; les PDF multi-pages sont neanmoins
geres (une page imprimee par page PDF).
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF : pixelise les pages PDF (deja utilise par src/pdf_to_jpg.py)
import win32print
import win32ui
from PIL import Image, ImageDraw, ImageFont, ImageWin

# Index GetDeviceCaps : resolution imprimable, taille physique, marges non imprimables.
_HORZRES = 8
_VERTRES = 10
_PHYSICALWIDTH = 110
_PHYSICALHEIGHT = 111
_PHYSICALOFFSETX = 112
_PHYSICALOFFSETY = 113

_RASTER_DPI = 200  # rendu PDF -> image (aligne sur src/pdf_to_jpg.py)
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".gif"}


def list_printers() -> list[str]:
    """Noms des imprimantes installees (locales + connexions reseau), triees."""
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    # Niveau 1 (PRINTER_INFO_1) : le nom est en index 2 de chaque tuple.
    printers = win32print.EnumPrinters(flags)
    return sorted({p[2] for p in printers})


def default_printer() -> str | None:
    """Imprimante par defaut de Windows, ou None si indisponible."""
    try:
        return win32print.GetDefaultPrinter() or None
    except Exception:  # noqa: BLE001  (aucune imprimante installee, etc.)
        return None


def _pages_as_images(path: Path) -> list[Image.Image]:
    """Charge le document en une liste d'images RGB (une par page a imprimer)."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        images: list[Image.Image] = []
        doc = fitz.open(path)
        try:
            matrix = fitz.Matrix(_RASTER_DPI / 72.0, _RASTER_DPI / 72.0)
            for page in doc:
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                images.append(
                    Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                )
        finally:
            doc.close()
        return images
    if ext in _IMAGE_EXTS:
        return [Image.open(path).convert("RGB")]
    raise ValueError(f"Format non imprimable : {ext or path.name}")


def _print_images(images: list[Image.Image], printer_name: str, doc_name: str) -> None:
    """Imprime une suite d'images : chacune centree et agrandie au max de la zone
    imprimable en respectant le ratio (pas de deformation). Une page par image."""
    if not images:
        raise ValueError("Aucune page a imprimer.")

    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(printer_name)  # leve si l'imprimante est introuvable
    try:
        printable = (hdc.GetDeviceCaps(_HORZRES), hdc.GetDeviceCaps(_VERTRES))
        physical = (hdc.GetDeviceCaps(_PHYSICALWIDTH), hdc.GetDeviceCaps(_PHYSICALHEIGHT))
        offset = (hdc.GetDeviceCaps(_PHYSICALOFFSETX), hdc.GetDeviceCaps(_PHYSICALOFFSETY))
        hdc.StartDoc(doc_name)
        try:
            for img in images:
                hdc.StartPage()
                scale = min(printable[0] / img.width, printable[1] / img.height)
                w, h = int(img.width * scale), int(img.height * scale)
                # Centre dans la feuille physique, ramene au repere imprimable
                # (origine = coin haut-gauche imprimable) en retirant les marges.
                x = int((physical[0] - w) / 2) - offset[0]
                y = int((physical[1] - h) / 2) - offset[1]
                ImageWin.Dib(img).draw(hdc.GetHandleOutput(), (x, y, x + w, y + h))
                hdc.EndPage()
        finally:
            hdc.EndDoc()
    finally:
        hdc.DeleteDC()


def print_file(path, printer_name: str, *, doc_name: str | None = None) -> None:
    """Imprime `path` (JPG ou PDF) sur l'imprimante nommee, mise a l'echelle page.

    Leve une exception si le fichier est absent, le format non imprimable, ou
    l'imprimante introuvable (le statut/affichage est gere par l'appelant).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {path}")
    _print_images(_pages_as_images(path), printer_name, doc_name or path.stem)


def print_test_page(printer_name: str) -> None:
    """Imprime une page de test pour verifier le choix de l'imprimante."""
    img = Image.new("RGB", (1240, 1754), "white")  # ~A4 a 150 dpi
    draw = ImageDraw.Draw(img)
    try:
        title_font = ImageFont.truetype("arialbd.ttf", 64)
        body_font = ImageFont.truetype("arial.ttf", 40)
    except OSError:
        title_font = body_font = ImageFont.load_default()
    draw.text((120, 140), "Test d'impression", fill="black", font=title_font)
    draw.text((120, 260), "Cabinet Dr Aslem Gouiaa", fill="black", font=body_font)
    draw.text((120, 330), f"Imprimante : {printer_name}", fill="black", font=body_font)
    draw.rectangle((110, 120, 1130, 420), outline="black", width=3)
    _print_images([img], printer_name, "Test d'impression")
