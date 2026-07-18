"""Tests du module `crm.tray` : singleton mutex + boucle scheduler.

Les dépendances externes (pystray, service.run_once, mutex Win32) sont mockées
pour tester la logique de contrôle sans poser de vraie icône tray.
"""

from __future__ import annotations

import sys
import time
from unittest import mock

import pytest

from crm import tray


# -----------------------------------------------------------------------------
# Tests du singleton mutex
# -----------------------------------------------------------------------------


def test_acquire_singleton_non_windows_returns_truthy(monkeypatch):
    """Hors Windows, le singleton n'est pas appliqué → renvoie un handle truthy."""
    monkeypatch.setattr(tray.os, "name", "posix")
    handle = tray._acquire_singleton()
    assert handle  # truthy → l'instance continue


def test_acquire_singleton_windows_first_instance(monkeypatch):
    """Sur Windows, 1re instance : CreateMutex réussit, GetLastError = 0 → handle."""
    monkeypatch.setattr(tray.os, "name", "nt")

    fake_k32 = mock.MagicMock()
    fake_k32.CreateMutexW.return_value = 12345  # handle non-nul
    fake_ctypes = mock.MagicMock()
    fake_ctypes.windll.kernel32 = fake_k32
    fake_ctypes.get_last_error.return_value = 0  # pas ERROR_ALREADY_EXISTS

    monkeypatch.setattr(tray.ctypes, "windll", fake_ctypes.windll, raising=False) if hasattr(
        tray, "ctypes"
    ) else None
    # _acquire_singleton fait `import ctypes` localement → on patche sys.modules.
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)
    # wintypes est aussi importé localement.
    monkeypatch.setitem(sys.modules, "ctypes.wintypes", mock.MagicMock())

    handle = tray._acquire_singleton()
    assert handle == 12345


def test_acquire_singleton_windows_already_running(monkeypatch):
    """Sur Windows, si le mutex existe déjà → renvoie None (2e instance quitte)."""
    monkeypatch.setattr(tray.os, "name", "nt")

    fake_k32 = mock.MagicMock()
    fake_k32.CreateMutexW.return_value = 999  # un handle quand même retourné
    fake_ctypes = mock.MagicMock()
    fake_ctypes.windll.kernel32 = fake_k32
    fake_ctypes.get_last_error.return_value = 183  # ERROR_ALREADY_EXISTS

    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)
    monkeypatch.setitem(sys.modules, "ctypes.wintypes", mock.MagicMock())

    handle = tray._acquire_singleton()
    assert handle is None  # déjà lancé → l'appelant doit quitter
    # Le handle acquis sur le mutex existant doit être fermé.
    fake_k32.CloseHandle.assert_called_once_with(999)


# -----------------------------------------------------------------------------
# Tests de la boucle scheduler
# -----------------------------------------------------------------------------


def test_scheduler_loop_runs_one_cycle_then_stops(monkeypatch):
    """La boucle appelle service.run_once() puis s'arrête proprement sur stop()."""
    # run_once est la cible réelle — on la mocke pour éviter la DB.
    fake_run_once = mock.MagicMock(return_value=(0, [{"id": 1}]))
    monkeypatch.setattr(tray.service, "run_once", fake_run_once)
    # _current_interval lit la DB via sqlite3 → mock pour renvoyer un intervalle court.
    monkeypatch.setattr(tray._SchedulerLoop, "_current_interval", lambda self: 1)

    loop = tray._SchedulerLoop()
    loop.start()

    # Laisse le 1er cycle immédiat s'exécuter, puis stoppe.
    time.sleep(0.3)
    loop.stop()
    loop.join(timeout=5)

    assert not loop.is_alive()
    assert fake_run_once.call_count >= 1
    assert loop.last_processed_count == 1
    assert loop.last_error is None
    assert loop.last_cycle_at is not None


def test_scheduler_loop_survives_exception(monkeypatch):
    """Une exception dans run_once ne tue pas le thread (best-effort)."""
    fake_run_once = mock.MagicMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(tray.service, "run_once", fake_run_once)
    monkeypatch.setattr(tray._SchedulerLoop, "_current_interval", lambda self: 1)

    loop = tray._SchedulerLoop()
    loop.start()
    time.sleep(0.3)
    loop.stop()
    loop.join(timeout=5)

    assert not loop.is_alive()  # le thread a survécu à l'exception
    assert loop.last_error == "boom"
    assert loop.last_processed_count == 0


def test_scheduler_loop_respects_stop_during_sleep(monkeypatch):
    """stop() pendant le sleep de l'interval débloque immédiatement la boucle."""
    monkeypatch.setattr(tray.service, "run_once", lambda: (0, []))
    # Intervalle long pour s'assurer qu'on est dans le sleep au moment du stop.
    monkeypatch.setattr(tray._SchedulerLoop, "_current_interval", lambda self: 600)

    loop = tray._SchedulerLoop()
    t0 = time.time()
    loop.start()
    time.sleep(0.3)  # laisse le 1er cycle s'exécuter
    loop.stop()
    loop.join(timeout=5)
    elapsed = time.time() - t0

    assert not loop.is_alive()
    # Doit s'arrêter en ~0.3s, pas après 600 min de sleep.
    assert elapsed < 5
