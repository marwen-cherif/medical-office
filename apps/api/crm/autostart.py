"""Démarrage automatique du worker tray au logon (sans droits admin).

Inscrit le worker de fond (`crm-tray.exe` en prod, `python -m crm.tray` en dev)
dans la clé par-utilisateur :

    HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run

Cette clé est exécutée par Explorer au moment de la connexion de l'utilisateur
(équivalent du dossier « Démarrage », mais pilotable programmatiquement). Elle ne
requiert AUCUN droit administrateur — contrairement à un Service Windows
(Session 0, qui d'ailleurs ne pourrait ni afficher de toasts ni poser d'icône
tray, étant isolé du bureau depuis Vista).

Pourquoi pas une tâche planifiée (`schtasks`) ? L'ancienne implémentation
relançait `crm-server.exe --service` toutes les 15 min, ce qui faisait flasher
une console noire à chaque exécution (`crm-server.exe` est `console=True` pour
le handshake stdout de Tauri, et la tâche ne masque pas la fenêtre). Le worker
tray, lui, est `console=False` → aucune fenêtre, et il contient sa propre boucle
de planification interne (plus de relance périodique d'un exe).

API publique
------------
  install()            → bool  (pose la valeur Run, idempotent)
  uninstall()          → bool  (supprime la valeur)
  is_installed()       → bool  (True si la valeur existe et pointe sur l'exe courant)
  cleanup_legacy_task() → bool (supprime l'ancienne tâche
                                `schtasks` `CabinetCRM-RappelsService`)
"""

from __future__ import annotations

import logging
import subprocess
import sys
from typing import Optional

_log = logging.getLogger("crm.autostart")

# Clé Run par-utilisateur (HKCU) — exécutée par Explorer au logon, sans admin.
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
# Nom de la valeur dans la clé Run.
_VALUE_NAME = "CabinetCRM-Tray"

# Ancienne tâche planifiée (remplacée par le worker tray). On la supprime une
# fois pour migrer proprement sans laisser deux mécanismes concurrents.
_LEGACY_TASK_NAME = "CabinetCRM-RappelsService"


def _tray_command() -> Optional[str]:
    """Renvoie la commande à inscrire dans Run pour lancer le worker tray.

    En prod (exe PyInstaller frozen) : le chemin de `crm-tray.exe` (situé dans le
    même dossier que l'exécutable courant). On l'entoure de guillemets pour gérer les
    chemins avec espaces.

    En dev : on n'inscrit rien — `python -m crm.tray` dépend d'un environnement
    Python local qu'on ne peut pas supposer présent au prochain logon. Renvoie None.
    """
    if not getattr(sys, "frozen", False):
        return None
    from pathlib import Path
    tray_exe = Path(sys.executable).parent / "crm-tray.exe"
    return f'"{tray_exe}"'


def _start_tray_process(cmd: str) -> None:
    """Lance le worker tray en arrière-plan s'il n'est pas déjà actif (sans bloquer)."""
    try:
        exe_path = cmd.strip('"')
        subprocess.Popen(
            [exe_path],
            creationflags=0x08000000,  # CREATE_NO_WINDOW
            close_fds=True,
        )
        _log.info("Worker tray démarré à la volée : %s", exe_path)
    except Exception as exc:  # noqa: BLE001
        _log.warning("Impossible de lancer le worker tray à la volée : %s", exc)


def install() -> bool:
    """Inscrit le worker tray au démarrage (HKCU\\...\\Run). Idempotent. Sans admin.

    Renvoie True si inscrit (ou déjà inscrit avec la bonne valeur). Ne lève jamais.
    """
    cmd = _tray_command()
    if cmd is None:
        _log.info("Autostart tray non installé en mode dev (pas d'exe frozen).")
        return False

    if _set_run_value(cmd):
        _log.info("Worker tray inscrit au démarrage (HKCU Run) : %s", cmd)
        # Profite de l'occasion pour nettoyer l'ancienne tâche planifiée.
        cleanup_legacy_task()
        # Lance le tray immédiatement pour éviter de devoir attendre un reboot
        _start_tray_process(cmd)
        return True
    return False


def uninstall() -> bool:
    """Supprime l'inscription au démarrage. Renvoie True si supprimée (ou absente)."""
    if not _delete_run_value():
        return False
    _log.info("Worker tray retiré du démarrage (HKCU Run).")
    return True


def is_installed() -> bool:
    """True si la valeur Run existe et pointe sur l'exe tray courant."""
    cmd = _tray_command()
    if cmd is None:
        # En dev, on ne peut pas être « installé » (pas d'exe frozen).
        return False
    current = _read_run_value()
    # Comparaison tolérante aux différences de guillemets/chemins.
    return bool(current) and _normalize(current) == _normalize(cmd)


# =============================================================================
# Accès registre (HKCU) — best-effort, ne lève jamais
# =============================================================================


def _set_run_value(value: str) -> bool:
    """Pose `_VALUE_NAME`=`value` dans HKCU\\...\\Run. Renvoie False si échec."""
    try:
        import winreg

        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, value)
        return True
    except Exception as exc:  # noqa: BLE001
        _log.warning("Écriture HKCU Run échouée : %s", exc)
        return False


def _read_run_value() -> Optional[str]:
    """Lit la valeur `_VALUE_NAME` dans HKCU\\...\\Run, ou None si absente/erreur."""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ
        ) as key:
            value, _ = winreg.QueryValueEx(key, _VALUE_NAME)
            return str(value) if value else None
    except FileNotFoundError:
        return None
    except Exception as exc:  # noqa: BLE001
        _log.warning("Lecture HKCU Run échouée : %s", exc)
        return None


def _delete_run_value() -> bool:
    """Supprime `_VALUE_NAME` de HKCU\\...\\Run.

    Renvoie True si supprimée ou absente.
    """
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _VALUE_NAME)
        return True
    except FileNotFoundError:
        return True  # déjà absente → succès
    except Exception as exc:  # noqa: BLE001
        _log.warning("Suppression HKCU Run échouée : %s", exc)
        return False


def _normalize(cmd: str) -> str:
    """Normalise une commande Run pour comparaison (basse casse, sans guillemets)."""
    return cmd.strip().strip('"').lower()


# =============================================================================
# Migration : suppression de l'ancienne tâche planifiée schtasks
# =============================================================================


def cleanup_legacy_task() -> bool:
    """Supprime l'ancienne tâche planifiée `CabinetCRM-RappelsService` (schtasks).

    Best-effort : renvoie True si supprimée ou absente. À appeler une fois après
    migration vers le worker tray pour éviter deux mécanismes concurrents.
    """
    try:
        # /Query d'abord — évite de logguer un warning bruyant si déjà absente.
        check = subprocess.run(
            ["schtasks", "/Query", "/TN", _LEGACY_TASK_NAME, "/FO", "LIST"],
            capture_output=True,
            timeout=15,
            creationflags=0x08000000,  # CREATE_NO_WINDOW — ne pas flasher une console
        )
        if check.returncode != 0:
            # Déjà absente → rien à faire (cas normal après migration).
            return True
        dele = subprocess.run(
            ["schtasks", "/Delete", "/TN", _LEGACY_TASK_NAME, "/F"],
            capture_output=True,
            timeout=15,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        if dele.returncode == 0:
            _log.info(
                "Ancienne tâche planifiée « %s » supprimée (migration worker tray).",
                _LEGACY_TASK_NAME,
            )
            return True
        _log.warning(
            "Suppression ancienne tâche « %s » échouée (rc=%d).",
            _LEGACY_TASK_NAME,
            dele.returncode,
        )
        return False
    except Exception as exc:  # noqa: BLE001
        _log.warning("Cleanup ancienne tâche planifiée impossible : %s", exc)
        return False
