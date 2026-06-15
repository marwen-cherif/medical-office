@echo off
setlocal
cd /d "%~dp0"

echo === Installation des dependances ===
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Erreur installation dependances.
    pause
    exit /b 1
)

echo.
echo === Build 1/2 : application DESKTOP (Cabinet-CRM.exe) ===
pyinstaller --noconfirm --clean crm-desktop.spec
if errorlevel 1 (
    echo Erreur PyInstaller (desktop).
    pause
    exit /b 1
)

echo.
echo === Build 2/2 : application WEB (Cabinet-CRM-Web.exe) ===
pyinstaller --noconfirm --clean crm-web.spec
if errorlevel 1 (
    echo Erreur PyInstaller (web).
    pause
    exit /b 1
)

echo.
echo === Copie de config.ini et reset.bat a cote des .exe ===
copy /Y config.ini dist\config.ini >nul
copy /Y reset.bat dist\reset.bat >nul

echo.
echo Build OK. Les executables sont dans le dossier dist\ :
echo   - dist\Cabinet-CRM.exe       (application desktop)
echo   - dist\Cabinet-CRM-Web.exe   (application web / navigateur)
echo   - dist\reset.bat             (remise a zero des donnees)
echo.
echo A distribuer ensemble : les deux .exe, config.ini, reset.bat, et les
echo dossiers data\ templates\ input\ (crees au besoin a cote des .exe).
pause
