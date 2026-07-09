"""Point d'entree du backend de services (sidecar) du Cabinet CRM.

Lance la facade FastAPI (`crm/server.py`). Empaquete par PyInstaller
(`crm-server.spec`) en binaire externe, demarre par la coquille Tauri
(`externalBin`), qui lit le handshake `CRM_SERVER_READY {json}` sur son stdout
pour decouvrir le port ephemere et le jeton de session.

En dev, equivalent a : `python -m crm.server` (port ephemere, jeton auto).
"""

from crm.server import main

if __name__ == "__main__":
    main()
