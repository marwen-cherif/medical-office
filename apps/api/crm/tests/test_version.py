import sys
from unittest.mock import patch
from crm.version import app_version, app_version_full, build_tag, commit_tag, _frozen

def test_app_version():
    assert app_version() == "v1.0.0"

def test_frozen_check():
    # Test when not frozen
    with patch.object(sys, "frozen", False, create=True):
        assert not _frozen()
        
    # Test when frozen
    with patch.object(sys, "frozen", True, create=True):
        assert _frozen()

def test_build_tag_dev():
    with patch("crm.version._frozen", return_value=False):
        with patch("crm.version._git_short", return_value="abcdef"):
            assert build_tag() == "dev-abcdef"
        with patch("crm.version._git_short", return_value=""):
            assert build_tag() == "dev"

def test_build_tag_frozen():
    with patch("crm.version._frozen", return_value=True):
        with patch("crm.version._build_info", return_value={"build": "20260709-1234"}):
            assert build_tag() == "20260709-1234"
        with patch("crm.version._build_info", return_value={}):
            assert build_tag() == "build"

def test_commit_tag():
    with patch("crm.version._frozen", return_value=False):
        with patch("crm.version._git_short", return_value="abcdef"):
            assert commit_tag() == "abcdef"
            
    with patch("crm.version._frozen", return_value=True):
        with patch("crm.version._build_info", return_value={"commit": "abcdef123456"}):
            assert commit_tag() == "abcdef123456"

def test_app_version_full():
    with patch("crm.version.build_tag", return_value="dev-abcdef"):
        assert app_version_full() == "v1.0.0 · dev-abcdef"
