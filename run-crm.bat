@echo off
setlocal
cd /d "%~dp0"

REM Lance l'application CRM (interface Flet).
REM Variante navigateur : run-crm-web.bat.

where python >nul 2>nul
if errorlevel 1 (
    echo Python introuvable dans le PATH.
    pause
    exit /b 1
)

python -m pip install -r requirements.txt >nul 2>nul
python crm_app.py
if errorlevel 1 (
    echo.
    echo L'application s'est arretee avec une erreur.
    pause
)
