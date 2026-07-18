import pytest
import fitz
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.pdf_to_jpg import pdf_first_page_to_jpg


def test_pdf_first_page_to_jpg_ok(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    jpg_path = tmp_path / "test.jpg"

    # Create a small valid PDF using PyMuPDF (fitz)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Hello World")
    doc.save(pdf_path)
    doc.close()

    assert pdf_path.exists()

    # Call the conversion function
    res = pdf_first_page_to_jpg(pdf_path, jpg_path, dpi=100)
    assert res == jpg_path
    assert jpg_path.exists()
    assert jpg_path.stat().st_size > 0


def test_pdf_first_page_to_jpg_empty(tmp_path):
    pdf_path = tmp_path / "empty.pdf"
    jpg_path = tmp_path / "empty.jpg"

    # Write a dummy file so fitz.open doesn't fail on missing file
    pdf_path.write_text("%PDF-1.4...")

    mock_doc = MagicMock()
    mock_doc.page_count = 0

    with patch("fitz.open", return_value=mock_doc):
        with pytest.raises(ValueError, match="PDF vide"):
            pdf_first_page_to_jpg(pdf_path, jpg_path)
        
        mock_doc.close.assert_called_once()
