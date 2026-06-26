# -*- mode: python ; coding: utf-8 -*-
# Build du SIDECAR backend (crm-server.exe) : facade FastAPI reutilisant le moteur.
#
# Difference avec crm-desktop.spec (Flet) : pas de Flet/Flutter ; on embarque
# FastAPI + uvicorn (+ leurs deps) et le moteur (Word COM, impression, PDF).
#
# console=True : le sidecar DOIT pouvoir ecrire le handshake sur stdout (en mode
# windowed, Python n'a pas de stdout valide). La coquille Tauri demarre le sidecar
# SANS fenetre console (CREATE_NO_WINDOW), donc aucune console noire n'apparait.
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = [
    'win32com.client', 'pythoncom', 'fitz', 'docx', 'requests',
    'win32print', 'win32ui', 'win32gui', 'win32con',  # impression directe (crm/printing.py)
    'crm._build_info',                # genere par build (numero de build) ; absent = avertissement
    'uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan.on',
]
# FastAPI/uvicorn/pydantic + moteur : on collecte tout pour ne rien oublier
# (starlette, anyio, pydantic_core, etc. sont tires transitvement).
for pkg in ('fastapi', 'uvicorn', 'pydantic', 'starlette', 'win32com', 'docx', 'PIL'):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h


a = Analysis(
    ['crm_server.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['flet', 'flet_desktop'],  # le sidecar n'a pas d'UI Flet
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
    name='crm-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,           # stdout requis pour le handshake (fenetre masquee par Tauri)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.ico',
)
