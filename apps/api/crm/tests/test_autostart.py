"""Tests du module `crm.autostart` : inscription au démarrage (HKCU Run).

Le registre Windows et `sys.frozen` sont mockés pour tester la logique sans
toucher au vrai HKCU ni dépendre d'un exe PyInstaller.
"""

from __future__ import annotations

import builtins
import sys
from unittest import mock

import pytest

from crm import autostart


# -----------------------------------------------------------------------------
# Faux module winreg pour simuler la lecture/écriture/suppression dans HKCU\Run
# -----------------------------------------------------------------------------


class _FakeKey:
    """Simulation d'une clé registre : un dict partagé via la classe."""

    store: dict[str, dict[str, str]] = {}

    def __init__(self) -> None:
        self._subkey = autostart._RUN_KEY
        self.store.setdefault(self._subkey, {})

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def fake_registry(monkeypatch):
    """Remplace winreg par un faux module isolé (reset entre chaque test)."""
    store: dict[str, dict[str, str]] = {autostart._RUN_KEY: {}}

    class _FakeWinreg:
        HKEY_CURRENT_USER = "HKCU"
        KEY_SET_VALUE = 1
        KEY_READ = 2
        REG_SZ = 1

        class CreateKeyEx:
            def __init__(self, _root, subkey, _reserved, _access):
                self._subkey = subkey
                store.setdefault(subkey, {})

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        @staticmethod
        def SetValueEx(key_obj, name, _reserved, _type_, value):
            store[key_obj._subkey][name] = value

        @staticmethod
        def QueryValueEx(key_obj, name):
            sub = store.get(key_obj._subkey, {})
            if name not in sub:
                raise FileNotFoundError(name)
            return sub[name], 1

        @staticmethod
        def DeleteValue(key_obj, name):
            store.get(key_obj._subkey, {}).pop(name, None)

    class _FakeOpenKey:
        def __init__(self, _root, subkey, _reserved, _access):
            self._subkey = subkey

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    _FakeWinreg.OpenKey = _FakeOpenKey  # type: ignore[attr-defined]

    fake_module = mock.MagicMock()
    fake_module.HKEY_CURRENT_USER = "HKCU"
    fake_module.KEY_SET_VALUE = 1
    fake_module.KEY_READ = 2
    fake_module.REG_SZ = 1
    fake_module.CreateKeyEx = _FakeWinreg.CreateKeyEx
    fake_module.SetValueEx = _FakeWinreg.SetValueEx
    fake_module.QueryValueEx = _FakeWinreg.QueryValueEx
    fake_module.DeleteValue = _FakeWinreg.DeleteValue
    fake_module.OpenKey = _FakeOpenKey

    # Le module autostart fait `import winreg` à l'intérieur de chaque fonction
    # → on intercepte builtins.__import__ pour renvoyer le faux quand demandé.
    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "winreg":
            return fake_module
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    return store


# -----------------------------------------------------------------------------
# Tests _tray_command
# -----------------------------------------------------------------------------


def test_tray_command_dev_returns_none(monkeypatch):
    """En dev (pas frozen), aucune commande à inscrire → None."""
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert autostart._tray_command() is None


def test_tray_command_frozen_returns_quoted_exe(monkeypatch):
    """En prod frozen, renvoie le chemin de l'exe entouré de guillemets."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Program Files\Cabinet CRM\crm-tray.exe")
    cmd = autostart._tray_command()
    assert cmd == r'"C:\Program Files\Cabinet CRM\crm-tray.exe"'


# -----------------------------------------------------------------------------
# Tests install / uninstall / is_installed
# -----------------------------------------------------------------------------


def test_install_dev_does_nothing(monkeypatch):
    """En dev, install() ne lève pas et renvoie False (pas d'exe frozen)."""
    monkeypatch.delattr(sys, "frozen", raising=False)
    # cleanup_legacy_task appelle subprocess → on évite tout appel réel.
    monkeypatch.setattr(autostart, "cleanup_legacy_task", lambda: True)
    assert autostart.install() is False


def test_install_then_is_installed_roundtrip(monkeypatch, fake_registry):
    """install() pose la valeur Run ; is_installed() la détecte."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\App\crm-tray.exe")
    monkeypatch.setattr(autostart, "cleanup_legacy_task", lambda: True)

    assert autostart.is_installed() is False  # pas encore inscrit
    assert autostart.install() is True
    assert autostart.is_installed() is True


def test_install_idempotent(monkeypatch, fake_registry):
    """Installer deux fois ne lève pas et laisse une seule valeur."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\App\crm-tray.exe")
    monkeypatch.setattr(autostart, "cleanup_legacy_task", lambda: True)

    assert autostart.install() is True
    assert autostart.install() is True  # idempotent
    values = fake_registry[autostart._RUN_KEY]
    assert len(values) == 1


def test_uninstall_after_install(monkeypatch, fake_registry):
    """uninstall() supprime la valeur ; is_installed() devient False."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\App\crm-tray.exe")
    monkeypatch.setattr(autostart, "cleanup_legacy_task", lambda: True)

    autostart.install()
    assert autostart.is_installed() is True

    assert autostart.uninstall() is True
    assert autostart.is_installed() is False


def test_uninstall_when_absent_is_success(monkeypatch, fake_registry):
    """uninstall() renvoie True même si la valeur n'existe pas (idempotent)."""
    assert autostart.uninstall() is True


def test_is_installed_detects_stale_value(monkeypatch, fake_registry):
    """is_installed() renvoie False si la valeur pointe vers un autre exe."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\new\crm-tray.exe")
    monkeypatch.setattr(autostart, "cleanup_legacy_task", lambda: True)

    # Une valeur obsolète (ancien chemin d'install).
    fake_registry[autostart._RUN_KEY][autostart._VALUE_NAME] = r'"C:\old\crm-tray.exe"'
    assert autostart.is_installed() is False  # chemin différent → pas à jour


# -----------------------------------------------------------------------------
# Tests cleanup_legacy_task
# -----------------------------------------------------------------------------


def test_cleanup_legacy_task_absent_returns_true(monkeypatch):
    """Si l'ancienne tâche schtasks n'existe pas, cleanup renvoie True sans bruit."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        # Simule « tâche introuvable » → /Query retourne rc != 0.
        return mock.MagicMock(returncode=1)

    monkeypatch.setattr(autostart.subprocess, "run", fake_run)
    assert autostart.cleanup_legacy_task() is True
    # Un seul appel (Query) — pas de Delete puisque déjà absente.
    assert len(calls) == 1
    assert "/Query" in calls[0]


def test_cleanup_legacy_task_present_deletes(monkeypatch):
    """Si l'ancienne tâche existe, cleanup appelle /Delete."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if "/Query" in cmd:
            return mock.MagicMock(returncode=0)  # existe
        if "/Delete" in cmd:
            return mock.MagicMock(returncode=0)  # supprimée
        return mock.MagicMock(returncode=1)

    monkeypatch.setattr(autostart.subprocess, "run", fake_run)
    assert autostart.cleanup_legacy_task() is True
    assert len(calls) == 2
    assert "/Delete" in calls[1]
    assert autostart._LEGACY_TASK_NAME in " ".join(calls[1])
