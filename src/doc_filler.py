from __future__ import annotations

import re
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

# wdFormatPDF constant
WD_FORMAT_PDF = 17


class WordSession:
    """Context manager autour d'une instance Word COM unique."""

    def __init__(self):
        self._word = None
        self._pythoncom = None

    def __enter__(self):
        import pythoncom
        import win32com.client

        self._pythoncom = pythoncom
        pythoncom.CoInitialize()
        self._word = win32com.client.DispatchEx("Word.Application")
        self._word.Visible = False
        self._word.DisplayAlerts = 0
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self._word is not None:
                self._word.Quit(SaveChanges=0)
        finally:
            self._word = None
            if self._pythoncom is not None:
                self._pythoncom.CoUninitialize()
                self._pythoncom = None

    def fill_and_export_pdf(
        self,
        template_path: Path,
        replacements: dict[str, str],
        pdf_output: Path,
    ) -> Path:
        """Remplace les placeholders via python-docx, exporte en PDF via Word COM."""
        pdf_output.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmp:
            filled_docx = Path(tmp) / "filled.docx"
            _fill_docx(template_path, replacements, filled_docx)

            doc = self._word.Documents.Open(str(filled_docx), ReadOnly=False)
            try:
                doc.SaveAs(str(pdf_output), FileFormat=WD_FORMAT_PDF)
            finally:
                doc.Close(SaveChanges=0)

        return pdf_output


_PLACEHOLDER_RE = re.compile(r"<([A-Z0-9_]+)>")


def _p_elem_text(p_elem) -> str:
    """Texte concatene d'un paragraphe (element w:p), tous runs confondus."""
    return "".join(t.text or "" for t in p_elem.iter(qn("w:t")))


def extract_placeholders(template_path: Path) -> list[str]:
    """Liste les balises <TAG> presentes dans le .docx, dans l'ordre, sans doublon.

    Parcourt le corps, les zones de texte, et les en-tetes/pieds (meme traversee que
    `_fill_docx`). Une balise peut etre eclatee sur plusieurs runs : on reconstruit donc
    le texte complet de chaque paragraphe avant la recherche.
    """
    doc = Document(str(template_path))
    chunks: list[str] = []

    for para in doc.paragraphs:
        chunks.append(para.text)
    for txbx in doc.element.body.iter(qn("w:txbxContent")):
        for p_elem in txbx.iter(qn("w:p")):
            chunks.append(_p_elem_text(p_elem))
    for section in doc.sections:
        for para in section.header.paragraphs:
            chunks.append(para.text)
        for para in section.footer.paragraphs:
            chunks.append(para.text)

    seen: dict[str, None] = {}
    for text in chunks:
        for match in _PLACEHOLDER_RE.findall(text):
            seen.setdefault(match, None)
    return list(seen.keys())


def _fill_docx(template_path: Path, replacements: dict[str, str], output_path: Path) -> None:
    """Remplace les placeholders dans tous les paragraphes du docx (corps + zones de texte)."""
    doc = Document(str(template_path))

    # Corps principal
    for para in doc.paragraphs:
        _replace_in_para(para, replacements)

    # Zones de texte (w:txbxContent)
    for txbx in doc.element.body.iter(qn("w:txbxContent")):
        for p_elem in txbx.iter(qn("w:p")):
            _replace_in_para_elem(p_elem, replacements)

    # En-têtes et pieds de page
    for section in doc.sections:
        for para in section.header.paragraphs:
            _replace_in_para(para, replacements)
        for para in section.footer.paragraphs:
            _replace_in_para(para, replacements)

    doc.save(str(output_path))


def _replace_in_para(para, replacements: dict[str, str]) -> None:
    _replace_in_para_elem(para._element, replacements)


_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def _replace_in_para_elem(p_elem, replacements: dict[str, str]) -> None:
    runs = list(p_elem.iter(qn("w:r")))
    if not runs:
        return

    # Collect (run, w:t element, current text) for each run
    run_data = []
    for r in runs:
        t = r.find(qn("w:t"))
        run_data.append([r, t, t.text if (t is not None and t.text) else ""])

    full_text = "".join(rd[2] for rd in run_data)
    new_full = full_text
    for ph, val in replacements.items():
        new_full = new_full.replace(ph, val)

    if new_full == full_text:
        return

    # Redistribute new_full back to runs.
    # Build a character → run-index map for the original text.
    char_run = []
    for i, rd in enumerate(run_data):
        char_run.extend([i] * len(rd[2]))

    # For each placeholder occurrence, find the span of runs it covers,
    # assign the replacement value to the first run of that span and
    # blank out the others. Rebuild new run texts in one pass.
    new_run_texts = [rd[2] for rd in run_data]

    for ph, val in replacements.items():
        ph_len = len(ph)
        start = 0
        while True:
            idx = "".join(new_run_texts).find(ph, start)
            if idx < 0:
                break
            end = idx + ph_len

            # Rebuild a fresh char_run from current new_run_texts
            cr = []
            for i, t in enumerate(new_run_texts):
                cr.extend([i] * len(t))

            first = cr[idx] if idx < len(cr) else None
            last = cr[end - 1] if end - 1 < len(cr) else None
            if first is None or last is None:
                break

            # Compute prefix and suffix within the first/last runs
            first_run_start = sum(len(new_run_texts[i]) for i in range(first))
            prefix = new_run_texts[first][: idx - first_run_start]

            last_run_start = sum(len(new_run_texts[i]) for i in range(last))
            suffix = new_run_texts[last][end - last_run_start :]

            # Use the run containing the middle character of the placeholder
            # so the replacement inherits the dominant formatting (e.g. bold)
            mid_char = idx + ph_len // 2
            mid_run = cr[mid_char] if mid_char < len(cr) else first

            # Empty all runs before mid_run (they held the start of the placeholder)
            new_run_texts[first] = prefix
            for i in range(first + 1, mid_run):
                new_run_texts[i] = ""
            # mid_run is always entirely inside the placeholder span, so no prefix
            new_run_texts[mid_run] = val + (suffix if mid_run == last else "")
            # Empty runs after mid_run up to (but not including) last
            for i in range(mid_run + 1, last + 1):
                new_run_texts[i] = suffix if i == last else ""

            start = idx + len(val)

    # Write back to runs (converting newlines into <w:br/> line breaks)
    for rd, new_text in zip(run_data, new_run_texts):
        r, t_elem, old_text = rd
        if new_text == old_text:
            continue
        _set_run_text(r, t_elem, new_text)


def _set_run_text(r, t_elem, text: str) -> None:
    """Ecrit `text` dans le run `r`, en transformant les retours a la ligne
    (\\n) en elements <w:br/> pour qu'ils soient rendus par Word."""
    from lxml import etree

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    if "\n" not in text:
        if t_elem is None:
            t_elem = etree.SubElement(r, qn("w:t"))
        t_elem.text = text
        if text and text != text.strip():
            t_elem.set(_XML_SPACE, "preserve")
        elif _XML_SPACE in t_elem.attrib and text == text.strip():
            del t_elem.attrib[_XML_SPACE]
        return

    # Multi-ligne : on reconstruit le contenu du run avec des <w:br/>.
    # On retire les anciens noeuds de texte/saut, on garde <w:rPr> (le style).
    for child in list(r):
        if child.tag in (qn("w:t"), qn("w:br"), qn("w:cr")):
            r.remove(child)

    for i, line in enumerate(text.split("\n")):
        if i > 0:
            etree.SubElement(r, qn("w:br"))
        t = etree.SubElement(r, qn("w:t"))
        t.text = line
        t.set(_XML_SPACE, "preserve")


def format_montant(value: float) -> str:
    return f"{value:,.3f}".replace(",", " ").replace(".", ",")
