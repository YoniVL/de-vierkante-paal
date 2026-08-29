@echo off
REM Maakt een bureaublad-snelkoppeling "De Vierkante Paal" (opent de tool, geen venster).
REM Vraagt daarna of ze ook bij het opstarten van Windows mag meestarten.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo Draai eerst 'start.bat' zodat de omgeving geinstalleerd is.
    pause & goto :eof
)

REM logo-icoon aanmaken
".venv\Scripts\python.exe" -m dvp.assets >nul 2>nul

set "TARGET=%~dp0.venv\Scripts\pythonw.exe"
set "ARGS=%~dp0dvp\launch.py"
set "WORKDIR=%~dp0"
set "ICON=%~dp0dvp\static\logo.ico"
if not exist "%ICON%" set "ICON=%SystemRoot%\System32\SHELL32.dll,220"

powershell -NoProfile -Command ^
  "$w=New-Object -ComObject WScript.Shell;" ^
  "$s=$w.CreateShortcut([IO.Path]::Combine($w.SpecialFolders('Desktop'),'De Vierkante Paal.lnk'));" ^
  "$s.TargetPath='%TARGET%'; $s.Arguments='\"%ARGS%\"'; $s.WorkingDirectory='%WORKDIR%';" ^
  "$s.IconLocation='%ICON%'; $s.Save()"

echo.
echo Snelkoppeling "De Vierkante Paal" staat nu op je bureaublad.
echo.
choice /c JN /m "Ook automatisch meestarten met Windows"
if errorlevel 2 goto :eof

powershell -NoProfile -Command ^
  "$w=New-Object -ComObject WScript.Shell;" ^
  "$s=$w.CreateShortcut([IO.Path]::Combine($w.SpecialFolders('Startup'),'De Vierkante Paal.lnk'));" ^
  "$s.TargetPath='%TARGET%'; $s.Arguments='\"%ARGS%\"'; $s.WorkingDirectory='%WORKDIR%'; $s.Save()"

echo Toegevoegd aan Opstarten. Vanaf de volgende herstart draait de tool altijd op de achtergrond.
echo (Verwijderen kan via Taakbeheer ^> Opstarten-apps, of de map "shell:startup".)
pause
