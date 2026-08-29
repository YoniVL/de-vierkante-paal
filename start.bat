@echo off
REM ==============================================================
REM  De Vierkante Paal - voorbereidingstool
REM  Dubbelklik dit bestand. Het venster sluit vanzelf; de tool
REM  draait daarna onzichtbaar op de achtergrond.
REM  Maak eenmalig een snelkoppeling: dubbelklik 'snelkoppeling-maken.bat'.
REM ==============================================================
setlocal
cd /d "%~dp0"

set "PYEXE=py"
where py >nul 2>nul || set "PYEXE=python"

if not exist ".venv\Scripts\pythonw.exe" (
    echo [setup] Eenmalige installatie ^(1 minuut^)...
    %PYEXE% -m venv .venv || goto :fail
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail
    echo [setup] Klaar.
)

REM Start onzichtbaar en open de browser; dit venster sluit meteen.
".venv\Scripts\pythonw.exe" dvp\launch.py
goto :eof

:fail
echo.
echo [fout] Setup mislukt. Is Python 3.11+ geinstalleerd ^(met "Add to PATH"^)?
pause
