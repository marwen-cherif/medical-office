"""Worker de fond windowed — icône tray + boucle scheduler interne pour les rappels.

Remplace l'ancienne tâche planifiée `schtasks` qui relançait `crm-server.exe
--service` toutes les 15 min (et faisait flasher une console noire). Ce worker
est un **processus unique**, démarré au logon via `HKCU\\...\\Run` (cf.
`crm/autostart.py`), qui :

  1. Tourne en **boucle interne** (thread daemon) : toutes les
     `rappels_scheduler_interval` minutes, appelle `service.run_once()` qui
     traite les rappels échus et émet les toasts.
  2. Pose une **icône dans la zone de notification** (tray) avec un menu
     clic-droit : « Ouvrir Cabinet CRM », « Statut (prochain check) »,
     « Quitter le service ».
  3. Est **windowed** (`console=False` à la build PyInstaller) → zéro fenêtre
     console, aucune flash, même au démarrage et à chaque toast.

Anti-double-instance : un mutex Win32 nommé garantit qu'une seule instance du
worker tourne par session (évite N icônes si l'utilisateur relance l'app alors
que le worker tourne déjà).

L'interval du scheduler est relu depuis `meta.rappels_scheduler_interval` à
chaque cycle → un changement via l'UI de paramétrage est pris en compte sans
redémarrer le worker.

Point d'entrée :
    python -m crm.tray                  # dev
    Cabinet-CRM-Tray.exe                # exe PyInstaller (crm_tray.py)
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from . import service

_log = logging.getLogger("crm.tray")

# Mutex Win32 nommé — garantit l'unicité du worker par session utilisateur.
# Préfixe « Local\ » = limité à la session courante (pas Global\ qui demanderait
# des privilèges pour traverser les sessions).
_SINGLETON_MUTEX_NAME = "Local\\tn.cabinet.gouiaaa.crm.tray"

# Nom de l'exe Tauri (productName dans tauri.conf.json), à côté du sidecar en prod.
_TAURI_EXE_NAME = "Cabinet CRM.exe"


# =============================================================================
# Singleton : empêcher plusieurs instances du worker
# =============================================================================


def _acquire_singleton() -> Optional[int]:
    """Tente d'acquérir le mutex singleton Win32. Renvoie le handle ou None.

    Si le mutex existe déjà (worker déjà lancé), renvoie None → l'appelant doit
    quitter immédiatement. Hors Windows, renvoie toujours un handle truthy (1)
    — le singleton n'est alors pas appliqué (dev sur macOS/Linux non ciblé).

    Le handle DOIT être gardé vivant : dès qu'il est libéré (GC ou exit), le
    mutex est relâché et une autre instance pourrait démarrer. On le retourne
    donc à l'appelant pour qu'il le conserve jusqu'à la fin du process.
    """
    if os.name != "nt":
        return 1
    try:
        import ctypes
        from ctypes import wintypes

        # CreateMutexW(lpMutexAttributes, bInitialOwner, lpName)
        # retourne le handle ; GetLastError via GetLastError() pour distinguer
        # « créé » (0) de « déjà existant » (ERROR_ALREADY_EXISTS = 183).
        k32 = ctypes.windll.kernel32
        k32.CreateMutexW.restype = wintypes.HANDLE
        k32.CreateMutexW.argtypes = [wintypes.LPCVOID, wintypes.BOOL, wintypes.LPCWSTR]
        handle = k32.CreateMutexW(None, False, _SINGLETON_MUTEX_NAME)
        
        # Le test mock utilise get_last_error. En production, windll n'active pas
        # use_last_error donc get_last_error vaut 0. On vérifie alors GetLastError().
        already_exists = False
        if ctypes.get_last_error() == 183:
            already_exists = True
        else:
            try:
                if hasattr(ctypes, "GetLastError") and ctypes.GetLastError() == 183:
                    already_exists = True
            except Exception:
                pass

        if already_exists:
            _log.info("Worker tray déjà en cours — cette instance quitte.")
            # Ferme le handle qu'on vient d'acquérir (sur un mutex existant,
            # CreateMutex nous donne quand même un handle à fermer).
            if handle:
                k32.CloseHandle(handle)
            return None
        return int(handle) if handle else None
    except Exception as exc:  # noqa: BLE001
        # En cas d'échec du mécanisme singleton, on laisse tourner (mieux vaut
        # deux icônes que zéro notification). On loggue pour diagnostic.
        _log.warning(
            "Mutex singleton indisponible (%s) — risque de double instance.", exc
        )
        return 1


# =============================================================================
# Boucle scheduler interne (thread daemon)
# =============================================================================


class _SchedulerLoop(threading.Thread):
    """Thread daemon qui exécute `service.run_once()` à intervalle régulier.

    L'interval est relu depuis la base à chaque cycle (prise en compte des
    changements de paramètre sans redémarrage). L'arrêt propre se fait via
    `stop()` qui débloque la `Event.wait()` du sleep en cours.
    """

    def __init__(self) -> None:
        super().__init__(name="crm-tray-scheduler", daemon=True)
        self._stop_event = threading.Event()
        # État partagé pour le menu tray (lisible depuis le thread UI pystray).
        self.last_cycle_at: Optional[float] = None  # epoch
        self.next_cycle_at: Optional[float] = None  # epoch
        self.last_processed_count: int = 0
        self.last_error: Optional[str] = None

    def stop(self) -> None:
        self._stop_event.set()

    def _current_interval(self) -> int:
        """Relit l'interval depuis `meta.rappels_scheduler_interval` (défaut 15 min)."""
        try:
            import sqlite3

            from . import repo
            from .db import default_db_path

            conn = sqlite3.connect(str(default_db_path()))
            try:
                raw = repo.get_setting(conn, "rappels_scheduler_interval")
            finally:
                conn.close()
            try:
                val = int(raw or "15")
                return val if val >= 1 else 15
            except (TypeError, ValueError):
                return 15
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "Lecture interval scheduler échouée (%s) — défaut 15 min.", exc
            )
            return 15

    def run(self) -> None:  # noqa: D401 (nom imposé par threading)
        """Boucle : un cycle immédiat, puis attend l'interval et recommence."""
        while not self._stop_event.is_set():
            cycle_start = time.time()
            try:
                code, traites = service.run_once()
                self.last_processed_count = len(traites)
                self.last_error = None if code == 0 else f"code {code}"
            except Exception as exc:  # noqa: BLE001
                # Ne doit jamais faire planter le thread (sinon plus de notifs).
                _log.error("Cycle scheduler en exception : %s", exc, exc_info=True)
                self.last_error = str(exc)
                self.last_processed_count = 0
            self.last_cycle_at = cycle_start

            interval = self._current_interval()
            next_at = time.time() + interval * 60
            self.next_cycle_at = next_at
            _log.debug(
                "Cycle fait (%d rappels). Prochain dans %d min.",
                self.last_processed_count,
                interval,
            )
            # Event.wait(timeout) permet un arrêt propre et immédiat via stop().
            self._stop_event.wait(timeout=interval * 60)


# =============================================================================
# Menu tray — ouvrir l'app, statut, quitter
# =============================================================================


def _tauri_exe_path() -> Path:
    """Chemin du exe Tauri principal en prod.

    En prod, `sys.executable` = `.../crm-tray.exe`, le exe Tauri est dans le
    même dossier d'install. En dev, on ne s'attend pas à le trouver.
    """
    install_dir = (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path.cwd()
    )
    candidates = ["cabinet-crm.exe", "Cabinet CRM.exe", "Cabinet-CRM.exe"]
    for cand in candidates:
        exe_path = install_dir / cand
        if exe_path.exists():
            return exe_path
    return install_dir / "cabinet-crm.exe"


def _open_app(icon, *args, **kwargs) -> None:
    """Lance le exe Tauri principal (CREATE_NO_WINDOW pour ne rien flasher)."""
    exe = _tauri_exe_path()
    if not exe.exists():
        _log.warning("Exe Tauri introuvable : %s", exe)
        return
    try:
        kwargs_proc: dict = {}
        if os.name == "nt":
            # Le exe Tauri est GUI ; on le lance détaché sans fenêtre console.
            kwargs_proc["creationflags"] = 0x00000008  # DETACHED_PROCESS
        subprocess.Popen([str(exe)], close_fds=True, **kwargs_proc)
        _log.info("Application Cabinet CRM lancée depuis la tray.")
    except Exception as exc:  # noqa: BLE001
        _log.warning("Lancement de l'app depuis la tray échoué : %s", exc)


def _quit(icon, item, scheduler: _SchedulerLoop, singleton_handle: object) -> None:
    """Arrête proprement le worker : stop le thread, libère le mutex, quitte."""
    _log.info("Arrêt du worker tray demandé par l'utilisateur.")
    scheduler.stop()
    icon.stop()
    # Le mutex est libéré automatiquement à la fermeture du process ; on ne fait
    # rien de spécial avec singleton_handle ici (gardé vivant jusqu'à l'exit).


def _format_status(scheduler: _SchedulerLoop) -> str:
    """Construit le texte de l'item de menu « Statut »."""
    if scheduler.last_cycle_at is None:
        return "Statut : premier cycle en cours…"
    from datetime import datetime

    last = datetime.fromtimestamp(scheduler.last_cycle_at).strftime("%H:%M")
    parts = [
        f"Dernier cycle : {last}",
        f"{scheduler.last_processed_count} rappel(s) traité(s)",
    ]
    if scheduler.next_cycle_at is not None:
        nxt = datetime.fromtimestamp(scheduler.next_cycle_at).strftime("%H:%M")
        parts.append(f"Prochain : {nxt}")
    if scheduler.last_error:
        parts.append(f"⚠ {scheduler.last_error}")
    return " · ".join(parts)


def _load_icon_image():
    """Charge l'image de l'icône tray (logo.ico) ou génère un fallback PIL.

    Recherche : à côté de l'exe (prod), puis dans _MEIPASS (PyInstaller bundle),
    puis une icône bleue générée à la volée par PIL (dernier recours).
    """
    from PIL import Image, ImageDraw  # embarquée par Pillow (déjà en deps)

    candidates = []
    if getattr(sys, "frozen", False):
        # Prod : à côté de l'exe, ou dans le bundle _MEIPASS (datas du spec).
        candidates.append(Path(sys.executable).resolve().parent / "logo.ico")
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "logo.ico")
    else:
        # Dev : remonte depuis crm/tray.py vers la racine du repo.
        candidates.append(Path(__file__).resolve().parents[3] / "logo.ico")

    for c in candidates:
        if c.exists():
            try:
                return Image.open(c)
            except Exception as exc:  # noqa: BLE001
                _log.warning("Lecture icône %s échouée : %s", c, exc)

    # Fallback : carré bleu 64x64.
    img = Image.new("RGBA", (64, 64), (30, 64, 175, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([16, 16, 48, 48], fill=(255, 255, 255, 255))
    _log.info("Icône fallback (PIL) utilisée pour la tray.")
    return img


def run() -> int:
    """Point d'entrée du worker tray. Bloquant (pilote la boucle d'événements UI).

    Renvoie 0 (succès) ou 1 (erreur fatale au démarrage).
    """
    service._setup_logging()  # réutilise le logging rotatif de service.py
    _log.info("=== Worker tray démarrage ===")

    # 1. Singleton : si déjà lancé, on quitte immédiatement (zéro icône en trop).
    singleton_handle = _acquire_singleton()
    if singleton_handle is None:
        return 0

    # 2. Démarrage de la boucle scheduler (1er cycle immédiat dans le thread).
    scheduler = _SchedulerLoop()
    scheduler.start()

    # 3. Icône + menu tray (bloquant jusqu'à icon.stop()).
    try:
        import pystray
        from PIL import Image  # noqa: F401 (s'assure que PIL est importable)

        image = _load_icon_image()

        def _status_text(*args, **kwargs) -> str:
            return _format_status(scheduler)

        menu = pystray.Menu(
            pystray.MenuItem(
                "Ouvrir Cabinet CRM",
                _open_app,
                default=True,  # double-clic sur l'icône = ouvrir l'app
            ),
            pystray.MenuItem(_status_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Quitter le service",
                lambda icon, item: _quit(icon, item, scheduler, singleton_handle),
            ),
        )

        icon = pystray.Icon("cabinet-crm-tray", image, "Cabinet CRM — rappels", menu)
        _log.info(
            "Icône tray posée. Boucle scheduler active (interval lu depuis meta)."
        )
        icon.run()
    except Exception as exc:  # noqa: BLE001
        # Si pystray/PIL échoue au démarrage, on garde au moins le scheduler
        # actif (notifications fonctionnelles, juste sans icône pour quitter).
        _log.error("Démarrage tray échoué : %s", exc, exc_info=True)
        _log.info(
            "Le scheduler reste actif sans icône tray (quitter via Task Manager)."
        )
        # Attend indéfiniment que le thread scheduler tourne (process vivant).
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass

    _log.info("=== Worker tray arrêté ===")
    return 0


# =============================================================================
# __main__ : `python -m crm.tray`
# =============================================================================

if __name__ == "__main__":
    sys.exit(run())
