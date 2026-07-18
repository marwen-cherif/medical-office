"""Point d'entree du WORKER TRAY de fond (rappels) du Cabinet CRM.

Empaquete par PyInstaller (`crm-tray.spec`) en binaire EXTERNE `crm-tray.exe`,
windowed (console=False) : aucune fenetre noire n'apparait, ni au demarrage, ni
lors des notifications. Lance l'icone tray + la boucle scheduler interne
(`crm/tray.py`).

Difference avec `crm-server.exe` (sidecar FastAPI) :
  - `crm-server.exe` : console=True (stdout requis pour le handshake Tauri),
    lance la facade HTTP pour l'UI React. Tue a la fermeture de l'app.
  - `crm-tray.exe`  : console=False, tourne en fond (autostart HKCU Run),
    survit a la fermeture de l'app pour continuer a emettre les toasts de
    rappels. C'est lui qui notifie quand l'app est fermee.

En dev : equivalent a `python -m crm.tray`.
"""

from crm.tray import run

if __name__ == "__main__":
    raise SystemExit(run())
