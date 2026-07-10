from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from crm.templates import (
    Template,
    _safe_name,
    create_template,
    delete_template,
    get_template,
    list_templates,
    open_in_word,
    rename_template,
    templates_dir,
)


@pytest.fixture
def mock_app_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("crm.templates.app_dir", lambda: tmp_path)
    return tmp_path


def test_safe_name():
    assert _safe_name("Modele A") == "modele_a"
    assert _safe_name("Modele   B") == "modele_b"
    assert _safe_name("Modele_@_A") == "modele_a"
    assert _safe_name("") == "modele"
    assert _safe_name("   ") == "modele"
    assert _safe_name("modèle") == "modèle"  # check alphanumeric translation
    assert _safe_name("a__b__c") == "a_b_c"


def test_template_label():
    t = Template(name="devis_type", path=Path("/dummy/path"))
    assert t.label == "Devis type"

    t2 = Template(name="note_honoraires_", path=Path("/dummy/path"))
    assert t2.label == "Note honoraires"


def test_templates_dir(mock_app_dir):
    d = templates_dir()
    assert d == mock_app_dir / "templates"
    assert d.exists()


def test_list_templates(mock_app_dir):
    d = templates_dir()
    # Create fake templates
    (d / "devis.docx").write_text("dummy")
    (d / "note.docx").write_text("dummy")
    (d / "~$temp.docx").write_text("dummy")  # should be ignored
    (d / "other.txt").write_text("dummy")  # should be ignored

    templates = list_templates()
    assert len(templates) == 2
    assert templates[0].name == "devis"
    assert templates[1].name == "note"


def test_get_template(mock_app_dir):
    d = templates_dir()
    (d / "test.docx").write_text("dummy")

    t = get_template("test")
    assert t is not None
    assert t.name == "test"
    assert t.path == d / "test.docx"

    assert get_template("nonexistent") is None


def test_create_template(mock_app_dir):
    d = templates_dir()
    
    # Test creation of a blank docx template
    # Mocking docx Document to avoid python-docx dependency issues in some envs
    with patch("docx.Document") as mock_doc:
        t = create_template("Fiche Patient")
        assert t.name == "fiche_patient"
        assert t.path == d / "fiche_patient.docx"
        assert mock_doc.called

    # Test error when template already exists
    (d / "fiche_patient.docx").write_text("dummy")
    with pytest.raises(FileExistsError):
        create_template("Fiche Patient")

    # Test copy from another template
    source = mock_app_dir / "source.docx"
    source.write_text("my source content")
    
    t_copy = create_template("Fiche Copie", copy_from=source)
    assert t_copy.name == "fiche_copie"
    assert t_copy.path.read_text() == "my source content"


def test_rename_template(mock_app_dir):
    d = templates_dir()
    t = Template(name="old_name", path=d / "old_name.docx")
    t.path.write_text("content")

    # Rename to identical name
    t_same = rename_template(t, "old_name")
    assert t_same.name == "old_name"
    assert t_same.path.exists()

    # Successful rename
    t_new = rename_template(t, "New Name")
    assert t_new.name == "new_name"
    assert t_new.path == d / "new_name.docx"
    assert t_new.path.exists()
    assert not (d / "old_name.docx").exists()

    # Try renaming when target already exists
    t_other = Template(name="other", path=d / "other.docx")
    t_other.path.write_text("other content")
    
    with pytest.raises(FileExistsError):
        rename_template(t_new, "other")


def test_delete_template(mock_app_dir):
    d = templates_dir()
    t = Template(name="test", path=d / "test.docx")
    t.path.write_text("content")

    assert t.path.exists()
    delete_template(t)
    assert not t.path.exists()

    # Deleting non-existent should not raise
    delete_template(t)


@patch("crm.templates.os.name", "nt")
@patch("crm.templates.os.startfile")
def test_open_in_word_windows(mock_startfile):
    t = Template(name="test", path=Path("dummy.docx"))
    open_in_word(t)
    mock_startfile.assert_called_once_with("dummy.docx")


@patch("crm.templates.sys.platform", "darwin")
@patch("crm.templates.os.name", "posix")
@patch("crm.templates.subprocess.Popen")
def test_open_in_word_mac(mock_popen):
    t = Template(name="test", path=Path("dummy.docx"))
    open_in_word(t)
    mock_popen.assert_called_once_with(["open", "dummy.docx"])


@patch("crm.templates.sys.platform", "linux")
@patch("crm.templates.os.name", "posix")
@patch("crm.templates.subprocess.Popen")
def test_open_in_word_linux(mock_popen):
    t = Template(name="test", path=Path("dummy.docx"))
    open_in_word(t)
    mock_popen.assert_called_once_with(["xdg-open", "dummy.docx"])
