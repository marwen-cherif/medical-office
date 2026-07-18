"""Service de fond headless — traitement des rappels échus.

Point d'entrée SANS interface graphique (pas de Flet, pas d'Uvicorn, pas de Word,
pas de Mailjet). Conçu pour être exécuté cycliquement par le worker tray
(`crm/tray.py`) :

    python -m crm.service                   # dev (un cycle)
    Cabinet-CRM-Tray.exe                    # exe PyInstaller : worker tray + boucle

`run_once()` effectue UN seul cycle de traitement. La boucle périodique (toutes
les `rappels_scheduler_interval` minutes) est portée par `crm/tray.py`, qui
appelle `run_once()` à chaque tick.

Flux d'exécution d'un cycle `run_once()` :
  1. Ouvre la base SQLite via `crm/db.connect()` (migrations + garde anti-downgrade).
  2. Lit les rappels `planifie` dont l'échéance est dépassée
     (`crm/rappels.traiter_rappels_dus`).
  3. Effectue la transition atomique planifie → du/a_envoyer avec horodatage.
  4. Si les notifications Windows sont activées (meta `rappels_notifs_enabled`),
     émet une notification Windows 11 native (toast) par rappel échu.
  5. Ferme la connexion et sort.

Idempotence : seuls les rappels à l'état `planifie` sont traités — un rappel déjà
`du`, `a_envoyer`, `envoye`, `traite` ou `annule` est ignoré, même si le cycle
se rejoue ou se chevauche.

Rattrapage après interruption : N rappels en retard → N notifications individuelles,
une par rappel échu (pas de regroupement).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from . import rappels as rappels_logic
from . import repo
from .db import SchemaTooNewError, connect

_log = logging.getLogger("crm.service")


# =============================================================================
# Notifications Windows 11 natives
# =============================================================================
#
# Chaîne d'émission (best-effort, ne lève jamais) :
#   1. PowerShell + ToastNotificationManager (WinRT)  → vraie toast Win10/11,
#      persiste dans le Centre de notifications, liée à l'AUMID de l'app,
#      fonctionne dans un process court (le service --service se termine en
#      quelques secondes — les anciens « balloon tips » disparaissaient avec lui).
#   2. win32gui.Shell_NotifyIcon (NIF_INFO)            → balloon legacy, secours.
#   3. plyer.notification                              → dernier recours.
#
# L'AUMID utilisée (`tn.cabinet.gouiaaa.crm`) est l'identifier Tauri de l'app
# (cf. apps/web/src-tauri/tauri.conf.json) : les toasts sont rattachées à l'app
# et restent visibles même quand le process émetteur s'arrête — indispensable
# pour le scénario « notifié même si l'application est fermée ».

# AUMID = identifier Tauri de l'app (cf. apps/web/src-tauri/tauri.conf.json).
# Doit être cohérent entre les toasts du service headless et l'app installée.
_TOAST_AUMID = "tn.cabinet.gouiaaa.crm"
_TOAST_APP_NAME = "Cabinet CRM"

# Mémo de l'enregistrement AUMID (registre + raccourci) pour ne pas le refaire
# à chaque toast. Réinitialisé à False à chaque démarrage de process.
_aumid_registered = False


def _ensure_aumid_registered() -> bool:
    """Enregistre l'AUMID dans le registre HKCU (requis Win10/11 non-MSIX).

    Sur Windows 10/11, une AUMID arbitraire (app desktop non empaquetée MSIX,
    comme Tauri NSIS / Electron / Python) ne peut afficher des toasts QUE si elle
    est déclarée dans le registre sous :
        HKCU\\Software\\Classes\\AppUserModelId\\<AUMID>
    avec au minimum `DisplayName`.

    Sans cela, `ToastNotificationManager::CreateToastNotifier(AUMID).Show(...)`
    réussit silencieusement côté API mais le toast n'apparaît jamais — c'est la
    cause n°1 des « notifications qui marchent pas » sur les apps desktop non
    empaquetées.

    Idempotent : ne recrée rien si déjà présent (CreateKeyEx est idempotent).
    Best-effort : ne lève jamais. Renvoie True si la clé a pu être posée.
    """
    if os.name != "nt":
        return False

    try:
        import winreg

        key_path = rf"Software\Classes\AppUserModelId\{_TOAST_AUMID}"
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, _TOAST_APP_NAME)
        _log.info("AUMID enregistrée dans HKCU : %s", _TOAST_AUMID)
        return True
    except Exception as exc:  # noqa: BLE001
        _log.warning("Enregistrement AUMID échoué : %s", exc)
        return False


def _xml_escape(s: str) -> str:
    """Échappement minimal XML pour injection dans le toast."""
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _notify_via_powershell(title: str, message: str) -> bool:
    """Émet une vraie toast Win10/11 via PowerShell + ToastNotificationManager.

    PowerShell est natif sur Windows 10/11 et embarque l'accès WinRT
    (`Windows.UI.Notifications`) — aucune dépendance Python supplémentaire et
    aucun paquet à collecter pour PyInstaller. Le XML du toast est base64-encodé
    (UTF-16LE) puis injecté dans un script .ps1 temporaire pour éviter tout
    problème d'échappement en ligne de commande.

    Renvoie True si le toast a pu être émis. Ne lève jamais.
    """
    import base64
    import os
    import subprocess
    import tempfile

    # Garde-fou : enregistre l'AUMID (registre + raccourci) si pas déjà fait.
    # Sans cela, Windows supprime silencieusement les toasts d'AUMID non déclarée.
    global _aumid_registered
    if not _aumid_registered:
        _aumid_registered = _ensure_aumid_registered()

    toast_xml = (
        "<toast>"
        "<visual>"
        '<binding template="ToastGeneric">'
        f"<text>{_xml_escape(title)}</text>"
        f"<text>{_xml_escape(message)}</text>"
        "</binding>"
        "</visual>"
        "</toast>"
    )
    # Base64 UTF-16LE : bulletproof contre tous les caractères (accents, \n, quotes).
    xml_b64 = base64.b64encode(toast_xml.encode("utf-16-le")).decode("ascii")

    ps_script = (
        "$ErrorActionPreference = 'Stop'\n"
        "[void][Windows.UI.Notifications.ToastNotificationManager, "
        "Windows.UI.Notifications, ContentType = WindowsRuntime]\n"
        "[void][Windows.Data.Xml.Dom.XmlDocument, "
        "Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]\n"
        "$Xml = New-Object Windows.Data.Xml.Dom.XmlDocument\n"
        "$Xml.LoadXml([System.Text.Encoding]::Unicode.GetString("
        f"[Convert]::FromBase64String('{xml_b64}')))\n"
        "$Toast = New-Object Windows.UI.Notifications.ToastNotification $Xml\n"
        f"[Windows.UI.Notifications.ToastNotificationManager]"
        f"::CreateToastNotifier('{_TOAST_AUMID}').Show($Toast)\n"
    )

    fd, tmp_path = tempfile.mkstemp(suffix=".ps1", prefix="crm_toast_")
    try:
        os.close(fd)
        # BOM UTF-8 : aide PowerShell à lire correctement les accents du script.
        with open(tmp_path, "w", encoding="utf-8-sig") as f:
            f.write(ps_script)
        # CREATE_NO_WINDOW (0x08000000) : PowerShell est un binaire console — sans
        # ce flag, une fenêtre noire flash à chaque toast (visible surtout quand
        # le worker tray tourne sans app ouverte). Ignoré silencieusement hors Windows.
        popen_kwargs: dict = {"capture_output": True, "text": True, "timeout": 15}
        if os.name == "nt":
            popen_kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                tmp_path,
            ],
            **popen_kwargs,
        )
        if result.returncode == 0:
            _log.info("Toast Windows 11 émis via PowerShell (AUMID=%s).", _TOAST_AUMID)
            return True
        _log.warning(
            "PowerShell toast échoué (rc=%d) : %s",
            result.returncode,
            (result.stderr or "")[:500],
        )
        return False
    except FileNotFoundError:
        _log.warning("powershell.exe introuvable — fallback ballon tray.")
        return False
    except subprocess.TimeoutExpired:
        _log.warning("PowerShell toast expiré (timeout) — fallback.")
        return False
    except Exception as exc:  # noqa: BLE001
        _log.warning("PowerShell toast en erreur : %s", exc)
        return False
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _notify_via_shell_notify_icon(title: str, message: str) -> bool:
    """Secours : balloon tip via pywin32 (win32gui.Shell_NotifyIcon, NIF_INFO).

    API legacy (Windows XP/7 era). Sur Windows 11 ces « balloon » sont souvent
    routés de façon inconsistante vers le Centre de notifications et peuvent
    être supprimés si le process émetteur se termine trop vite — d'où le statut
    de secours. Renvoie True si émis. Ne lève jamais.
    """
    try:
        import time

        import win32api  # type: ignore
        import win32con  # type: ignore
        import win32gui  # type: ignore

        wc = win32gui.WNDCLASS()
        wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = "CRMRappelNotif"
        wc.lpfnWndProc = {}  # dict = DefWindowProc
        try:
            class_atom = win32gui.RegisterClass(wc)
        except Exception:  # déjà enregistrée lors d'exécutions multiples
            class_atom = 0

        hwnd = win32gui.CreateWindow(
            "CRMRappelNotif",
            "TaskBar",
            0,
            0,
            0,
            win32con.CW_USEDEFAULT,
            win32con.CW_USEDEFAULT,
            0,
            0,
            wc.hInstance,
            None,
        )

        # NOTIFYICONDATA pour afficher le balloon (NIF_INFO).
        NIF_INFO = 0x00000010
        NIIF_INFO = 0x00000001
        nid = (
            hwnd,
            0,
            NIF_INFO,
            win32con.WM_USER + 20,
            0,
            "tooltip",
            message,
            200,
            title,
            NIIF_INFO,
        )
        win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
        win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, nid)
        time.sleep(2)
        # Nettoyage immédiat de l'icône tray (le balloon reste affiché
        # quelques secondes).
        win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (hwnd, 0))
        win32gui.DestroyWindow(hwnd)
        if class_atom:
            win32gui.UnregisterClass(wc.lpszClassName, wc.hInstance)
        _log.info("Balloon émis via pywin32/win32gui (secours).")
        return True
    except Exception as exc:  # noqa: BLE001
        _log.warning("Balloon pywin32 indisponible (erreur: %s).", exc)
        return False


def _notify_via_plyer(title: str, message: str) -> bool:
    """Dernier recours : plyer.notification (peut ne pas être installé)."""
    try:
        from plyer import notification  # type: ignore

        notification.notify(
            title=title, message=message, app_name=_TOAST_APP_NAME, timeout=10
        )
        _log.info("Notification émise via plyer (dernier recours).")
        return True
    except Exception as exc:  # noqa: BLE001
        _log.error("Fallback plyer échoué (erreur: %s).", exc, exc_info=True)
        return False


def _notify_windows(title: str, message: str) -> str | None:
    """Émet une notification Windows — chaîne PowerShell → win32gui → plyer.

    Renvoie le nom du moteur qui a réussi ('powershell' | 'win32gui' | 'plyer'),
    ou None si tous ont échoué. Best-effort : ne lève jamais — une erreur de
    notification ne doit pas faire échouer le service.
    """
    _log.info("Tentative d'émission d'une notification Windows : %s", title)
    if _notify_via_powershell(title, message):
        return "powershell"
    if _notify_via_shell_notify_icon(title, message):
        return "win32gui"
    if _notify_via_plyer(title, message):
        return "plyer"
    _log.error("Échec de toutes les méthodes de notification Windows.")
    return None


def _notifications_enabled(conn) -> bool:
    """Lit le réglage `rappels_notifs_enabled` depuis `meta` (défaut : True)."""
    val = repo.get_setting(conn, "rappels_notifs_enabled")
    # None (jamais défini) = activé par défaut ; "false" = désactivé explicitement.
    return val != "false"


def _build_toast_content(r: repo.Rappel, conn) -> tuple[str, str]:
    """Construit le titre et le corps du toast pour un rappel échu."""
    title = f"📅 Rappel : {r.titre}"
    if r.patient_id:
        patient = repo.get_patient(conn, r.patient_id)
        if patient:
            body = f"{patient.display} — {r.titre}"
        else:
            body = r.titre
    else:
        body = r.titre

    if r.type == "message_patient":
        body += "\n💬 Message WhatsApp à envoyer"
    else:
        body += "\n🔔 Alerte interne"

    return title, body


# =============================================================================
# Point d'entrée principal
# =============================================================================


def run_once(db_path: Path | None = None) -> tuple[int, list]:
    """Exécute UN cycle du service de fond : traite les rappels dus et notifie.

    Renvoie (code_sortie, rappels_traités) — code 0 = succès, 1 = erreur fatale.
    La liste des rappels traités (objets `Rappel`) permet au worker tray
    (`crm/tray.py`) d'afficher le statut (N rappels en attente / dernier cycle).

    La boucle périodique (toutes les N minutes) est portée par `crm/tray.py`,
    qui appelle cette fonction à chaque tick.
    """
    _log.info("Cycle rappels — démarrage.")

    try:
        conn = connect(db_path)
    except SchemaTooNewError as exc:
        _log.error("Base trop récente pour cette version de l'application : %s", exc)
        return 1, []
    except Exception as exc:  # noqa: BLE001
        _log.error("Impossible d'ouvrir la base de données : %s", exc)
        return 1, []

    try:
        notifs_enabled = _notifications_enabled(conn)
        _log.info(
            "Notifications Windows : %s.",
            "activées" if notifs_enabled else "désactivées",
        )

        # Traitement idempotent des rappels dus.
        traites = rappels_logic.traiter_rappels_dus(conn)
        _log.info("%d rappel(s) traité(s).", len(traites))

        for r in traites:
            _log.info(
                "Rappel #%d « %s » → état %s (type=%s).",
                r.id,
                r.titre,
                r.etat,
                r.type,
            )
            if notifs_enabled:
                title, body = _build_toast_content(r, conn)
                moteur = _notify_windows(title, body)
                _log.debug(
                    "Notification émise pour rappel #%d (moteur=%s).",
                    r.id,
                    moteur,
                )

    except Exception as exc:  # noqa: BLE001
        _log.error("Erreur inattendue durant le traitement : %s", exc, exc_info=True)
        return 1, []
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass

    _log.info("Cycle rappels — terminé (0 erreur).")
    return 0, traites


def run(db_path: Path | None = None) -> int:
    """Exécute UN cycle puis sort (compat `python -m crm.service`, `--service`).

    Renvoie le code de sortie (0 = succès, 1 = erreur fatale). La boucle
    périodique est portée par le worker tray (`crm/tray.py`) qui appelle
    `run_once()` à chaque tick — cette fonction `run()` n'exécute qu'un seul
    cycle, utile pour un test manuel ou un lancement one-shot.
    """
    _setup_logging()
    code, _ = run_once(db_path)
    return code


def _setup_logging() -> None:
    """Configure la journalisation vers un fichier rotatif à côté de la base.

    Ajoute aussi un `StreamHandler` sur stderr : le worker tray tourne en
    headless sans console attachée, mais en cas d'erreur fatale au boot (import
    manquant, crash avant le handlers fichiers), stderr reste capturé et
    consultable en dev (`python -m crm.service`) — sans cela, un échec
    silencieux laisserait un `service.log` vide.

    Best-effort : ne bloque jamais le démarrage.
    """
    try:
        import logging.handlers

        from .db import default_db_path

        fmt = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"
        )
        root = logging.getLogger()
        root.setLevel(logging.INFO)

        # 1. Fichier rotatif (destination principale).
        log_dir = default_db_path().parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "service.log",
            maxBytes=500_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)

        # 2. stderr : secours en cas de crash avant l'initialisation du fichier,
        #    ou pour le mode dev (`python -m crm.service`) où l'on veut la sortie
        #    console. `lastResort` de Python ne couvre que les WARNING+ sans
        #    formatter ; on ajoute donc un vrai handler INFO ici.
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(fmt)
        stream_handler.setLevel(logging.INFO)
        root.addHandler(stream_handler)
    except Exception:  # noqa: BLE001
        logging.basicConfig(level=logging.INFO)


# =============================================================================
# __main__ : `python -m crm.service`
# =============================================================================

if __name__ == "__main__":
    sys.exit(run())
