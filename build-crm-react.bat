@echo off
REM ============================================================================
REM Build de l'application CRM "React + sidecar" (Windows + Word requis).
REM
REM Produit un executable double-cliquable (installeur NSIS) : coquille Tauri
REM embarquant le sidecar Python (FastAPI) empaquete par PyInstaller.
REM
REM Prerequis (cf. ui/README.md) :
REM   - Python + deps : pip install -r requirements.txt
REM   - Node + npm
REM   - Rust (rustup) + Tauri CLI : npm i -g @tauri-apps/cli  (ou via npx)
REM
REM L'ancien build Flet (build-crm.bat) reste valide tant que Flet cohabite.
REM ============================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo [1/4] Build du sidecar Python (PyInstaller : crm-server.spec)...
pyinstaller --noconfirm --clean crm-server.spec || goto :error

echo [2/4] Detection du triple cible Rust...
for /f "tokens=2" %%i in ('rustc -Vv ^| findstr /b "host:"') do set TRIPLE=%%i
if "%TRIPLE%"=="" set TRIPLE=x86_64-pc-windows-msvc
echo     Triple = %TRIPLE%

echo [3/4] Copie du sidecar vers ui\src-tauri\binaries\crm-server-%TRIPLE%.exe ...
if not exist "ui\src-tauri\binaries" mkdir "ui\src-tauri\binaries"
copy /y "dist\crm-server.exe" "ui\src-tauri\binaries\crm-server-%TRIPLE%.exe" || goto :error

echo [4/4] Build du frontend + de la coquille Tauri (npm + cargo)...
cd ui
call npm ci || goto :error
call npm run tauri build || goto :error
cd ..

echo.
echo OK. Installeur dans ui\src-tauri\target\release\bundle\nsis\
goto :eof

:error
echo.
echo ECHEC du build (code %errorlevel%).
exit /b 1
