from pathlib import Path
import openpyxl
import pytest

from crm import repo
from crm.import_categories import (
    _clean_string,
    _parse_ordre,
    export_categories,
    export_categories_bytes,
    import_categories,
    write_template,
)


def test_clean_string():
    assert _clean_string("Hello ") == "Hello"
    assert _clean_string(None) is None
    assert _clean_string("") is None
    assert _clean_string("   ") is None
    assert _clean_string(123) == "123"


def test_parse_ordre():
    assert _parse_ordre(5) == 5
    assert _parse_ordre("10") == 10
    assert _parse_ordre("abc") == 0
    assert _parse_ordre(None) == 0
    assert _parse_ordre(True) == 0
    assert _parse_ordre(-3) == -3


def test_import_export_categories(test_db, tmp_path):
    wb_path = tmp_path / "import.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Categories"

    # Header row
    ws.append(["Nom", "Couleur", "Icone", "Ordre", "Message WhatsApp"])
    # Valid rows
    ws.append(["Consultation", "#ff0000", "user", 2, "Bonjour <PRENOM>"])
    ws.append(["Ordonnance", "#00ff00", "file", 1, "Voici l'ordo"])
    # Row with empty name (should be skipped)
    ws.append([None, "#0000ff", "image", 3, "Ignored"])

    wb.save(wb_path)
    wb.close()

    # Import in dry_run mode
    summary = import_categories(wb_path, dry_run=True, conn=test_db)
    assert summary.created == 2
    assert summary.updated == 0
    assert summary.skipped == 0
    assert len(summary.errors) == 0

    # Verify no categories were actually inserted in dry_run
    cats = repo.list_categories(test_db)
    assert len(cats) == 0

    # Import in normal mode
    summary = import_categories(wb_path, dry_run=False, conn=test_db)
    assert summary.created == 2
    assert summary.updated == 0
    assert summary.skipped == 0

    # Verify categories are in database
    cats = repo.list_categories(test_db)
    assert len(cats) == 2

    c_consult = repo.get_category(test_db, "Consultation")
    assert c_consult is not None
    assert c_consult.couleur == "#ff0000"
    assert c_consult.icone == "user"
    assert c_consult.sort_order == 2
    assert c_consult.whatsapp_message == "Bonjour <PRENOM>"

    # Run import with updates and a new row (checking idempotency)
    wb_path2 = tmp_path / "import_update.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active

    # Custom headers
    ws.append(["libelle", "hex", "icon", "sort", "whatsapp"])
    ws.append(["Consultation", "#aaaaaa", "user-updated", 5, "Bonjour updated"])
    ws.append(["Nouveau", "#111111", "star", 3, "Nouveau msg"])

    wb.save(wb_path2)
    wb.close()

    summary2 = import_categories(wb_path2, dry_run=False, conn=test_db)
    assert summary2.created == 1  # Nouveau
    assert summary2.updated == 1  # Consultation
    assert summary2.skipped == 0

    # Check update results
    c_consult_updated = repo.get_category(test_db, "Consultation")
    assert c_consult_updated.couleur == "#aaaaaa"
    assert c_consult_updated.icone == "user-updated"
    assert c_consult_updated.sort_order == 5
    assert c_consult_updated.whatsapp_message == "Bonjour updated"

    # Check new category creation
    c_new = repo.get_category(test_db, "Nouveau")
    assert c_new is not None
    assert c_new.couleur == "#111111"
    assert c_new.icone == "star"
    assert c_new.sort_order == 3
    assert c_new.whatsapp_message == "Nouveau msg"

    # Test export to excel
    export_path = tmp_path / "export.xlsx"
    count = export_categories(export_path, conn=test_db)
    assert count == 3  # Consultation, Ordonnance, Nouveau
    assert export_path.exists()

    # Read back exported workbook to verify structure
    wb_exported = openpyxl.load_workbook(export_path, read_only=True)
    ws_exported = wb_exported.active
    rows = list(ws_exported.iter_rows(values_only=True))
    wb_exported.close()

    assert rows[0] == ("Nom", "Couleur", "Icone", "Ordre", "Message WhatsApp")
    # Should list categories sorted by name or order
    assert len(rows) == 4

    # Test export to bytes
    exported_bytes, exported_count = export_categories_bytes(conn=test_db)
    assert exported_count == 3
    assert len(exported_bytes) > 0

    # Test template writing
    tpl_path = tmp_path / "template.xlsx"
    write_template(tpl_path)
    assert tpl_path.exists()

    wb_tpl = openpyxl.load_workbook(tpl_path, read_only=True)
    assert wb_tpl.active.title == "Categories"
    wb_tpl.close()


def test_import_categories_error_handling(test_db, tmp_path):
    # Test error when file is not found
    with pytest.raises(FileNotFoundError):
        import_categories(Path("nonexistent.xlsx"), conn=test_db)
