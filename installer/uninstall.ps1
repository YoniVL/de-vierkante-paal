# =====================================================================
#  De Vierkante Paal - verwijderen
#  Dit script staat in de installatiemap; het verwijdert die map,
#  de snelkoppelingen en de Windows-registratie.
# =====================================================================
$ErrorActionPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Windows.Forms

$APPNAAM = 'De Vierkante Paal'
$PORT    = 8756
$DOEL    = Split-Path -Parent $MyInvocation.MyCommand.Path
$REGKEY  = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\DeVierkantePaal'

$antwoord = [System.Windows.Forms.MessageBox]::Show(
    "$APPNAAM verwijderen?`n`nMap: $DOEL",
    "$APPNAAM verwijderen", 'YesNo', 'Question')
if ($antwoord -ne 'Yes') { return }

$bewaarData = [System.Windows.Forms.MessageBox]::Show(
    "Je bewaarde afleveringen en opgehaalde data behouden?`n`n" +
    "Ja  = de mappen 'data' en 'afleveringen' blijven staan.`n" +
    "Nee = alles wordt verwijderd.",
    'Gegevens behouden?', 'YesNo', 'Question')

# 1. draaiende server stoppen
try {
    $wc = New-Object System.Net.WebClient
    $wc.UploadString("http://127.0.0.1:$PORT/afsluiten", 'POST', '') | Out-Null
} catch { }
Start-Sleep -Milliseconds 500
Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" |
    Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($DOEL) } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# 2. snelkoppelingen (bureaublad, Opstarten, menu Start)
foreach ($d in @([Environment]::GetFolderPath('Desktop'),
                 [Environment]::GetFolderPath('Startup'),
                 [Environment]::GetFolderPath('Programs'))) {
    $lnk = Join-Path $d "$APPNAAM.lnk"
    if (Test-Path $lnk) { Remove-Item $lnk -Force }
}

# 3. registratie
Remove-Item $REGKEY -Recurse -Force

# 4. mappen
if ($bewaarData -eq 'Yes') {
    foreach ($sub in 'python', 'dvp') {
        $p = Join-Path $DOEL $sub
        if (Test-Path $p) { Remove-Item $p -Recurse -Force }
    }
    foreach ($f in 'logo.ico', 'versie.txt') {
        $p = Join-Path $DOEL $f
        if (Test-Path $p) { Remove-Item $p -Force }
    }
    [System.Windows.Forms.MessageBox]::Show(
        "$APPNAAM is verwijderd.`n`nJe gegevens staan nog in:`n$DOEL",
        $APPNAAM, 'OK', 'Information') | Out-Null
} else {
    # de hele map weg, inclusief dit script -> via een losse .bat in %TEMP%
    $bat = Join-Path $env:TEMP 'dvp-verwijder.bat'
    @"
@echo off
ping -n 3 127.0.0.1 >nul
rmdir /s /q "$DOEL"
del "%~f0"
"@ | Set-Content -Path $bat -Encoding ASCII
    [System.Windows.Forms.MessageBox]::Show("$APPNAAM is verwijderd.", $APPNAAM, 'OK', 'Information') | Out-Null
    Start-Process cmd.exe -ArgumentList '/c', $bat -WindowStyle Hidden
}
