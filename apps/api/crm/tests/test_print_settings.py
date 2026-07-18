import json
from crm import repo
from crm.print_settings import all_settings, get_settings_for, set_settings_for, PRINT_SETTINGS_KEY


def test_print_settings_empty_db(test_db):
    # If PRINT_SETTINGS_KEY is absent
    assert all_settings(test_db) == {}
    assert get_settings_for(test_db, "facture") == {"paper": None, "color": None}


def test_print_settings_invalid_json(test_db):
    # Invalid JSON
    repo.set_setting(test_db, PRINT_SETTINGS_KEY, "invalid-json")
    assert all_settings(test_db) == {}

    # Non-dictionary JSON
    repo.set_setting(test_db, PRINT_SETTINGS_KEY, json.dumps([1, 2, 3]))
    assert all_settings(test_db) == {}


def test_print_settings_filtering(test_db):
    # JSON with invalid keys or values
    data = {
        "facture": {"paper": "A4", "color": "color"},
        "invalid_doc": {"paper": "A10", "color": "blue"},
        123: {"paper": "A4"},  # Non-string key
        "missing_details": None,  # Non-dictionary value
    }
    repo.set_setting(test_db, PRINT_SETTINGS_KEY, json.dumps(data))
    
    settings = all_settings(test_db)
    assert "facture" in settings
    assert settings["facture"] == {"paper": "A4", "color": "color"}
    
    assert "invalid_doc" in settings
    assert settings["invalid_doc"] == {"paper": None, "color": None}
    
    assert 123 not in settings
    assert "missing_details" not in settings


def test_get_and_set_settings(test_db):
    # Set settings
    set_settings_for(test_db, "facture", "A4", "mono")
    assert get_settings_for(test_db, "facture") == {"paper": "A4", "color": "mono"}

    # Update with some None/invalid values
    set_settings_for(test_db, "facture", "A5", "invalid")
    assert get_settings_for(test_db, "facture") == {"paper": "A5", "color": None}

    # Set another document type
    set_settings_for(test_db, "devis", "A4", "color")
    assert get_settings_for(test_db, "devis") == {"paper": "A4", "color": "color"}
    
    # Remove one (both None)
    set_settings_for(test_db, "facture", None, None)
    assert get_settings_for(test_db, "facture") == {"paper": None, "color": None}
    # check that devis is still there
    assert get_settings_for(test_db, "devis") == {"paper": "A4", "color": "color"}
