# -*- mode: python ; coding: utf-8 -*-
# Build du WORKER TRAY de fond (crm-tray.exe) : icone tray + scheduler interne.
#
# Ce worker est DIFFERENT du sidecar FastAPI (crm-server.spec) :
#   - console=False  : AUCUNE fenetre console. Indispensable car le worker tourne
#                      en fond au logon (HKCU Run) et doit etre invisible (ni au
#                      demarrage, ni lors des toasts). Contrairement a crm-server
#                      qui a besoin de stdout pour le handshake Tauri, celui-ci
#                      n'a aucune sortie console a fournir.
#   - pas de FastAPI/uvicorn : le worker n'expose pas d'API HTTP. Il ne fait que
#                      traiter les rappels (crm.service.run_once) + poser une
#                      icone tray (pystray) en boucle interne.
#   - survit a la fermeture de l'app : c'est lui qui notifie quand l'app Tauri
#                      est fermee (rappels periodiques + toasts).
#
# Logo : embarque en datas pour l'icone tray (et un fallback PIL en secours).
from PyInstaller.utils.hooks import collect_all

datas = [('../../logo.ico', '.')]  # icone tray a cote de l'exe / dans _MEIPASS
binaries = []
hiddenimports = [
    # pystray backend Windows + Pillow (deja en deps pour l'impression).
    'pystray', 'pystray._win32',
    'PIL', 'PIL.Image', 'PIL.ImageDraw',
    # Moteur rappels + DB + repo (identique au sidecar pour la partie service).
    'crm.rappels', 'crm.service', 'crm.tray', 'crm.autostart',
    'crm.db', 'crm.repo',
    # win32 pour la chaine de secours des notifications (win32gui balloon) et
    # pour le mutex singleton (ctypes.windll, pas d'import win32 requis ici).
    'win32api', 'win32con', 'win32gui',
    'crm._build_info',  # genere par build ; absent = avertissement
]
# Pillow et pywin32 : collecte explicite (extensions natives a embarquer).
for pkg in ('PIL', 'win32com'):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h


a = Analysis(
    ['crm_tray.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Le worker n'est PAS un serveur HTTP : on exclut la stack web lourde
        # pour reduire la taille du bundle et eviter d'embarquer l'inutile.
        'flet', 'flet_desktop',
        'fastapi', 'uvicorn', 'starlette',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='crm-tray',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # CLE : aucune fenetre console (worker de fond invisible)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='../../logo.ico',
)
