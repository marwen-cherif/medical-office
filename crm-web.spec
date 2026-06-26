# -*- mode: python ; coding: utf-8 -*-
# Build de la webapp CRM : serveur local ouvert dans le navigateur (Cabinet-CRM-Web.exe).
from PyInstaller.utils.hooks import collect_all

# Logos embarques dans l'exe (icone fenetre + logo du menu lateral).
datas = [
    ('logo.ico', '.'),
    ('logo.png', '.'),
    ('logo_mark.png', '.'),
]
binaries = []
hiddenimports = [
    'win32com.client', 'pythoncom', 'fitz', 'docx', 'requests',
    'uvicorn', 'websockets',
    'win32print', 'win32ui', 'win32gui', 'win32con',  # impression directe (crm/printing.py)
    'crm._build_info',  # genere par build-crm.bat (numero de build) ; absent = avertissement
]
# Embarque le coeur de Flet (datas : controls/material/icons.json, etc.), les assets
# web de Flet + le serveur (uvicorn/fastapi) + back-end.
for pkg in ('flet', 'flet_web', 'uvicorn', 'fastapi', 'win32com', 'docx', 'PIL'):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h


a = Analysis(
    ['crm_web.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='Cabinet-CRM-Web',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,           # garde une fenetre : affiche l'URL et arrete le serveur a la fermeture
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.ico',
)
