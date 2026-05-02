@echo off
setlocal EnableDelayedExpansion

echo =====================================================
echo  WindowsToLinux - EXE Build
echo =====================================================
echo.

REM ---- Python vorhanden? --------------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo FEHLER: Python nicht im PATH gefunden.
    echo Bitte Python 3.12 oder neuer installieren und
    echo dem PATH hinzufuegen.
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo %PYVER% gefunden.

REM ---- GTK-DLLs vorhanden? (WeasyPrint-Anforderung) ----
where libcairo-2.dll >nul 2>&1
if errorlevel 1 (
    echo.
    echo WARNUNG: libcairo-2.dll nicht im PATH gefunden.
    echo WeasyPrint benoetigt die GTK3-Laufzeitbibliotheken.
    echo.
    echo Installation via MSYS2:
    echo   1. MSYS2 von https://www.msys2.org installieren
    echo   2. Im MinGW-w64-Terminal ausfuehren:
    echo        pacman -S mingw-w64-x86_64-gtk3
    echo   3. C:\msys64\mingw64\bin dem Windows-PATH hinzufuegen
    echo.
    echo Ohne GTK wird der PDF-Export nicht funktionieren.
    echo Build wird trotzdem gestartet...
    echo.
)

REM ---- Abhaengigkeiten installieren ---------------------
echo Installiere / pruefe Python-Abhaengigkeiten...
pip install -e ".[dev]" --quiet
if errorlevel 1 (
    echo FEHLER: pip install fehlgeschlagen.
    exit /b 1
)

pip install pyinstaller --quiet
if errorlevel 1 (
    echo FEHLER: PyInstaller-Installation fehlgeschlagen.
    exit /b 1
)

REM ---- Build starten ------------------------------------
echo.
echo Starte PyInstaller-Build...
echo.
python -m PyInstaller windowstolinux.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo =====================================================
    echo  BUILD FEHLGESCHLAGEN
    echo =====================================================
    echo.
    echo Haeufige Ursachen:
    echo   - GTK3 nicht installiert oder nicht im PATH
    echo   - Fehlende Python-Abhaengigkeiten
    echo   - Antivirus blockiert PyInstaller-Build-Prozess
    echo.
    exit /b 1
)

echo.
echo =====================================================
echo  Build erfolgreich!
echo =====================================================
echo.
echo Ausgabe:  dist\WindowsToLinux.exe
echo.
echo HINWEIS:
echo   Windows Defender und SmartScreen koennen die EXE
echo   beim ersten Start als unbekannte Software melden.
echo   Das ist ein Fehlalarm bei unsignierten EXEs.
echo   Im Dialog auf "Weitere Informationen" und dann
echo   "Trotzdem ausfuehren" klicken.
echo.
endlocal
