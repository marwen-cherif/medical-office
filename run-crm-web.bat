@echo off
setlocal
cd /d "%~dp0"

REM Lance l'application CRM en mode web (s'ouvre dans le navigateur).
REM Variante navigateur de run-crm.bat. Garder cette fenetre ouverte
REM pendant l'utilisation ; la fermer arrete le serveur.

where python >nul 2>nul
if errorlevel 1 (
    echo Python introuvable dans le PATH.
    pause
    exit /b 1
)

python -m pip install -r requirements.txt >nul 2>nul

set CRM_WEB=1
REM Decommenter pour acceder depuis un autre appareil du reseau local :
REM set CRM_HOST=0.0.0.0

python crm_web.py
if errorlevel 1 (
    echo.
    echo L'application s'est arretee avec une erreur.
    pause
)
