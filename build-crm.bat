@echo off
setlocal
cd /d "%~dp0"

echo === Generation du numero de build (crm\_build_info.py) ===
rem Horodatage du build (change a chaque build) + hash git court pour la tracabilite.
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmm"') do set BUILDSTAMP=%%i
set GITHASH=
for /f %%i in ('git rev-parse --short HEAD 2^>nul') do set GITHASH=%%i
> crm\_build_info.py echo BUILD = "%BUILDSTAMP%"
>> crm\_build_info.py echo COMMIT = "%GITHASH%"
echo   build = %BUILDSTAMP%  (commit %GITHASH%)

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
    echo Erreur PyInstaller ^(desktop^).
    pause
    exit /b 1
)

echo.
echo === Build 2/2 : application WEB (Cabinet-CRM-Web.exe) ===
pyinstaller --noconfirm --clean crm-web.spec
if errorlevel 1 (
    echo Erreur PyInstaller ^(web^).
    pause
    exit /b 1
)

echo.
echo === Copie de config.ini, reset.bat et prompts\ a cote des .exe ===
copy /Y config.ini dist\config.ini >nul
copy /Y reset.bat dist\reset.bat >nul
rem prompts\ : prompts IA editables (resolus via le dossier de l'exe au runtime).
xcopy /Y /I /E prompts dist\prompts >nul

echo.
echo Build OK. Les executables sont dans le dossier dist\ :
echo   - dist\Cabinet-CRM.exe       (application desktop)
echo   - dist\Cabinet-CRM-Web.exe   (application web / navigateur)
echo   - dist\reset.bat             (remise a zero des donnees)
echo   - dist\prompts\              (prompts IA editables)
echo.
echo A distribuer ensemble : les deux .exe, config.ini, reset.bat, prompts\, et les
echo dossiers data\ templates\ input\ (crees au besoin a cote des .exe).
pause
