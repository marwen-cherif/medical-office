@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
chcp 65001 >nul

REM Import du referentiel d'actes (libelle, prix, code) depuis un fichier Excel.
REM - Generer un modele vide a remplir, OU importer un .xlsx deja rempli.
REM - Glisser-deposer un .xlsx sur ce .bat l'importe directement.
REM Fonctionne a cote de l'exe distribue (Cabinet-CRM.exe) OU en dev (Python).
REM L'import est idempotent : relancer le meme fichier met a jour sans dupliquer,
REM et une sauvegarde de la base est prise avant ecriture.

REM --- Choix du lanceur : exe distribue si present, sinon Python ----------------
set "USE_EXE="
if exist "%~dp0Cabinet-CRM.exe" set "USE_EXE=1"
if not defined USE_EXE (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Ni Cabinet-CRM.exe ni Python introuvables : import impossible.
        pause
        exit /b 1
    )
)

REM --- Glisser-deposer : un fichier passe en argument est importe directement ---
if not "%~1"=="" (
    set "FICHIER=%~1"
    goto :import
)

:menu
echo ===============================================================
echo  IMPORT DES ACTES - Cabinet Dr Aslem Gouiaa (CRM)
echo ===============================================================
echo.
echo   [1] Generer un modele Excel vide a remplir
echo   [2] Importer un fichier Excel rempli
echo   [3] Exporter le referentiel vers Excel (pour l'editer puis le reimporter)
echo   [4] Quitter
echo.
echo  Astuce : vous pouvez aussi glisser-deposer un .xlsx sur ce fichier.
echo.
set "CHOIX="
set /p "CHOIX=Votre choix [1/2/3/4] : "
if "%CHOIX%"=="1" goto :modele
if "%CHOIX%"=="2" goto :demande
if "%CHOIX%"=="3" goto :export
if "%CHOIX%"=="4" exit /b 0
echo Choix invalide.
echo.
goto :menu

:modele
set "OUT=modele_actes.xlsx"
echo.
echo Generation du modele "%OUT%"...
call :run --modele "%OUT%"
if errorlevel 1 (
    echo.
    echo Erreur pendant la generation du modele.
    pause
    exit /b 1
)
echo.
echo Modele cree : %~dp0%OUT%
echo Ouvrez-le, remplissez les colonnes Libelle / Prix / Code / Categorie
echo (Code et Categorie facultatifs ; la Categorie classe les actes), enregistrez,
echo puis relancez ce fichier pour l'importer.
pause
exit /b 0

:export
set "OUT=referentiel_actes.xlsx"
echo.
echo Export du referentiel vers "%OUT%"...
call :run --export "%OUT%" --inclure-inactifs
if errorlevel 1 (
    echo.
    echo Erreur pendant l'export.
    pause
    exit /b 1
)
echo.
echo Export cree : %~dp0%OUT%
echo Editez les lignes (NE MODIFIEZ PAS la colonne ID : elle sert au rapprochement),
echo ajoutez de nouvelles lignes en laissant leur ID vide, enregistrez, puis
echo relancez ce fichier pour reimporter et mettre a jour.
pause
exit /b 0

:demande
echo.
set "FICHIER="
set /p "FICHIER=Chemin du fichier .xlsx a importer : "
REM Retire d'eventuels guillemets autour du chemin saisi.
set "FICHIER=%FICHIER:"=%"
if "%FICHIER%"=="" (
    echo Aucun fichier indique.
    pause
    exit /b 1
)

:import
if not exist "%FICHIER%" (
    echo.
    echo Fichier introuvable : %FICHIER%
    pause
    exit /b 1
)
echo.
echo Import de "%FICHIER%" en cours...
call :run "%FICHIER%"
if errorlevel 1 (
    echo.
    echo Erreur pendant l'import.
    pause
    exit /b 1
)
echo.
echo Import termine.
pause
exit /b 0

REM --- Sous-routine : dispatch exe distribue / Python --------------------------
:run
if defined USE_EXE (
    "%~dp0Cabinet-CRM.exe" --import-actes %*
) else (
    python -m crm.import_actes %*
)
exit /b %errorlevel%
