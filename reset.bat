@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul

REM Remise a zero : vide la base et supprime les notes generees (output/).
REM input/ (template, classeur patients) et config.ini sont conserves.
REM Fonctionne a cote de l'exe distribue (Cabinet-CRM.exe) OU en dev (Python).

echo ===============================================================
echo  REMISE A ZERO - Cabinet Dr Aslem Gouiaa (CRM)
echo ===============================================================
echo.
echo  Cette action est IRREVERSIBLE. Vont etre supprimes :
echo    - la base de donnees  : data\cabinet.db (toutes les fiches)
echo    - les notes generees  : output\ (.jpg / .pdf)
echo    - les fichiers de log : logs\
echo.
echo  Conserves : templates\ et config.ini.
echo  Au prochain lancement, l'app demarre sur une base vide (etat "neuf").
echo.

set "REP="
set /p "REP=Tapez SUPPRIMER puis Entree pour confirmer : "
if /I not "%REP%"=="SUPPRIMER" (
    echo.
    echo Annule : aucune donnee supprimee.
    pause
    exit /b 1
)

echo.
echo Remise a zero en cours...

if exist "%~dp0Cabinet-CRM.exe" (
    REM Distribution : l'exe fait la suppression (--yes : pas de 2e confirmation).
    "%~dp0Cabinet-CRM.exe" --reset --yes
) else (
    REM Dev : repli sur Python.
    where python >nul 2>nul
    if errorlevel 1 (
        echo Ni Cabinet-CRM.exe ni Python introuvables : impossible de reinitialiser.
        pause
        exit /b 1
    )
    python -m crm.reset --yes
)

if errorlevel 1 (
    echo.
    echo Erreur pendant la remise a zero.
    pause
    exit /b 1
)

echo.
echo Remise a zero effectuee.
pause
