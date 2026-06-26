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

import logging
from pathlib import Path

import fitz  # PyMuPDF : pixelise les pages PDF (deja utilise par src/pdf_to_jpg.py)
import win32con
import win32gui
import win32print
import win32ui
from PIL import Image, ImageDraw, ImageFont, ImageWin

# --- Journalisation -----------------------------------------------------------
# L'impression echouait silencieusement (DEVMODE jamais applique, exceptions
# avalees) : impossible a diagnostiquer. On journalise donc le parcours complet
# dans `logs/print.log` a cote de l'app, en plus de la console.
_logger = logging.getLogger("crm.printing")


def _get_logger() -> logging.Logger:
    """Logger « crm.printing », configure une seule fois (fichier + console).

    Best-effort : si le fichier de log ne peut pas etre cree (droits, etc.),
    on garde au moins la console. Ne leve jamais — la journalisation ne doit
    pas empecher l'impression.
    """
    if getattr(_logger, "_crm_configured", False):
        return _logger
    _logger.setLevel(logging.INFO)
    _logger.propagate = False
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    _logger.addHandler(logging.StreamHandler())
    _logger.handlers[-1].setFormatter(fmt)
    try:
        from crm.db import app_dir  # import tardif : evite tout cycle a l'import

        log_dir = app_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / "print.log", encoding="utf-8")
        fh.setFormatter(fmt)
        _logger.addHandler(fh)
    except Exception:  # noqa: BLE001  (pas de fichier de log : on garde la console)
        pass
    _logger._crm_configured = True  # type: ignore[attr-defined]
    return _logger


# Index GetDeviceCaps : resolution imprimable, taille physique, marges non imprimables.
_HORZRES = 8
_VERTRES = 10
_PHYSICALWIDTH = 110
_PHYSICALHEIGHT = 111
_PHYSICALOFFSETX = 112
_PHYSICALOFFSETY = 113

_RASTER_DPI = 200  # rendu PDF -> image (aligne sur src/pdf_to_jpg.py)
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".gif"}

# --- DEVMODE : format papier et couleur (valeurs stables de wingdi.h) ----------
# On les definit en clair plutot que de dependre de win32con : ces constantes ne
# changent pas. Appliquees au DEVMODE de l'imprimante avant le rendu (cf.
# _build_devmode) pour imprimer en A4/A5 et couleur/N&B sans boite de dialogue.
DMPAPER_A4 = 9
DMPAPER_A5 = 11
DMCOLOR_MONOCHROME = 1
DMCOLOR_COLOR = 2
# Bits `Fields` signalant au pilote quels champs du DEVMODE sont significatifs.
_DM_PAPERSIZE = 0x00000002
_DM_COLOR = 0x00000800

# Mappe les valeurs memorisees (cf. crm/print_settings.py) vers les codes DM.
_PAPER_TO_DM = {"A4": DMPAPER_A4, "A5": DMPAPER_A5}
_COLOR_TO_DM = {"color": DMCOLOR_COLOR, "mono": DMCOLOR_MONOCHROME}


def _build_devmode(printer_name: str, paper: str | None, color: str | None):
    """Construit un DEVMODE modifie (format/couleur) ou None si rien a appliquer.

    Repli sur None — donc impression au DEVMODE par defaut — si `paper`/`color`
    sont absents/inconnus, si l'imprimante n'expose pas de DEVMODE, ou en cas
    d'echec (cf. exigence « Tolerance aux capacites du pilote »). Ne leve jamais.

    Subtilite format papier : si le DEVMODE par defaut declare une taille
    explicite (`DM_PAPERLENGTH`/`DM_PAPERWIDTH`, ex. A4), certains pilotes la
    privilegient sur `PaperSize`. On efface donc ces bits en passant a un format
    standard, puis on laisse le pilote revalider/derive les dimensions via
    `DocumentProperties` (best-effort).
    """
    log = _get_logger()
    paper_dm = _PAPER_TO_DM.get(paper or "")
    color_dm = _COLOR_TO_DM.get(color or "")
    if paper_dm is None and color_dm is None:
        if paper or color:
            log.warning("Reglage ignore (valeur inconnue): paper=%r color=%r", paper, color)
        return None
    try:
        handle = win32print.OpenPrinter(printer_name)
        try:
            devmode = win32print.GetPrinter(handle, 2)["pDevMode"]
            if devmode is None:
                log.warning("Imprimante %r sans DEVMODE : format/couleur non appliques",
                            printer_name)
                return None
            if paper_dm is not None:
                devmode.PaperSize = paper_dm
                devmode.Fields |= _DM_PAPERSIZE
                # Efface les dimensions explicites perimees (sinon A4 « colle »).
                devmode.Fields &= ~(win32con.DM_PAPERLENGTH | win32con.DM_PAPERWIDTH)
            if color_dm is not None:
                devmode.Color = color_dm
                devmode.Fields |= _DM_COLOR
            # Revalidation par le pilote : derive PaperLength/Width du PaperSize.
            try:
                win32print.DocumentProperties(
                    0, handle, printer_name, devmode, devmode,
                    win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER)
            except Exception as exc:  # noqa: BLE001
                log.warning("DocumentProperties a echoue (%s) : on garde le DEVMODE brut", exc)
        finally:
            win32print.ClosePrinter(handle)
        log.info("DEVMODE construit: paper=%s (DM=%s) color=%s (DM=%s)",
                 paper, paper_dm, color, color_dm)
        return devmode
    except Exception:  # noqa: BLE001  (pilote capricieux : on retombe sur le defaut)
        log.warning("Construction du DEVMODE impossible pour %r (repli sur defaut)",
                    printer_name, exc_info=True)
        return None


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


def _print_images(
    images: list[Image.Image],
    printer_name: str,
    doc_name: str,
    devmode=None,
) -> None:
    """Imprime une suite d'images : chacune centree et agrandie au max de la zone
    imprimable en respectant le ratio (pas de deformation). Une page par image.

    Si `devmode` est fourni (format/couleur, cf. _build_devmode), il est applique
    au DC via `win32gui.ResetDC` avant de lire les capacites — l'echelle se
    recalcule donc sur le format effectif (A4->A5 reajuste automatiquement).
    `win32ui.CreateDC` n'expose PAS de methode `ResetDC` : on passe par
    `win32gui.ResetDC` sur le HDC brut (`GetSafeHdc`). Un echec est journalise
    mais non bloquant : on imprime alors au DEVMODE par defaut."""
    log = _get_logger()
    if not images:
        raise ValueError("Aucune page a imprimer.")

    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(printer_name)  # leve si l'imprimante est introuvable
    try:
        if devmode is not None:
            before = (hdc.GetDeviceCaps(_PHYSICALWIDTH), hdc.GetDeviceCaps(_PHYSICALHEIGHT))
            try:
                if not win32gui.ResetDC(hdc.GetSafeHdc(), devmode):
                    log.warning("ResetDC a renvoye 0 : DEVMODE non applique (format par defaut)")
            except Exception:  # noqa: BLE001  (pilote refusant le DEVMODE : on continue)
                log.warning("ResetDC a echoue : impression au DEVMODE par defaut", exc_info=True)
            after = (hdc.GetDeviceCaps(_PHYSICALWIDTH), hdc.GetDeviceCaps(_PHYSICALHEIGHT))
            # Taille physique en 1/1000 mm via LOGPIXELS ? Non : en pixels device.
            # On la journalise telle quelle ; un changement before!=after confirme
            # que le format a bien ete pris en compte par le pilote.
            log.info("Taille physique (px device) avant=%s apres=%s", before, after)
        # GetDeviceCaps lu APRES ResetDC : reflet du format effectivement applique.
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


def print_file(
    path,
    printer_name: str,
    *,
    paper: str | None = None,
    color: str | None = None,
    doc_name: str | None = None,
) -> None:
    """Imprime `path` (JPG ou PDF) sur l'imprimante nommee, mise a l'echelle page.

    `paper` (`"A4"`/`"A5"`) et `color` (`"color"`/`"mono"`) appliquent format et
    couleur via le DEVMODE de l'imprimante (cf. _build_devmode). A `None` (ou
    valeur inconnue), on n'y touche pas : impression au reglage par defaut de
    l'imprimante (comportement anterieur). Un format non supporte par le pilote
    retombe silencieusement sur son defaut.

    Leve une exception si le fichier est absent, le format non imprimable, ou
    l'imprimante introuvable (le statut/affichage est gere par l'appelant).
    """
    path = Path(path)
    _get_logger().info("Impression: fichier=%s imprimante=%r paper=%r color=%r",
                       path.name, printer_name, paper, color)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {path}")
    devmode = _build_devmode(printer_name, paper, color)
    _print_images(_pages_as_images(path), printer_name, doc_name or path.stem, devmode)


def print_test_page(
    printer_name: str,
    *,
    paper: str | None = None,
    color: str | None = None,
) -> None:
    """Imprime une page de test pour verifier le choix de l'imprimante.

    `paper` (`"A4"`/`"A5"`) et `color` (`"color"`/`"mono"`) appliquent format et
    couleur via le DEVMODE (cf. _build_devmode) — permet de verifier qu'un pilote
    honore bien ces reglages avant de les memoriser par type de document. A None
    (ou valeur inconnue), on imprime au reglage par defaut de l'imprimante.
    """
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
    # Recapitule les reglages testes pour controle visuel sur la feuille imprimee.
    paper_label = {"A4": "A4", "A5": "A5"}.get(paper or "", "défaut imprimante")
    color_label = {"color": "Couleur", "mono": "Noir & blanc"}.get(
        color or "", "défaut imprimante")
    draw.text((120, 400), f"Format : {paper_label}", fill="black", font=body_font)
    draw.text((120, 470), f"Couleur : {color_label}", fill="black", font=body_font)
    draw.rectangle((110, 120, 1130, 560), outline="black", width=3)
    devmode = _build_devmode(printer_name, paper, color)
    _print_images([img], printer_name, "Test d'impression", devmode)
