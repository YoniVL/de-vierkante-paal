# =====================================================================
#  Bouwt alle 4 de deelbestanden in één keer:
#    - Installeer De Vierkante Paal.exe   (Windows, DVP)
#    - Installeer Aftrap.exe              (Windows, generiek)
#    - De Vierkante Paal (Mac).zip        (Mac, DVP)
#    - Aftrap (Mac).zip                   (Mac, generiek)
#
#  Draai:  powershell -ExecutionPolicy Bypass -File installer\bouw-alles.ps1
#  Nodig: internet (eenmalig) + Python in PATH.
# =====================================================================
$ErrorActionPreference = 'Stop'
$inst = $PSScriptRoot
$uit  = Join-Path $inst 'uit'

function Kop($t) { Write-Host "`n######## $t ########`n" -ForegroundColor Cyan }

Kop 'Tests'
Push-Location (Split-Path -Parent $inst)
try {
    & py -W ignore -m unittest discover -s tests
    if ($LASTEXITCODE -ne 0) { throw 'tests falen — eerst fixen (of  py tests\opnemen.py  om de fixtures te vernieuwen)' }
} finally { Pop-Location }

Kop 'Windows — De Vierkante Paal'
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $inst 'bouw-installer.ps1')
if ($LASTEXITCODE -ne 0) { throw 'DVP-installer mislukt' }

Kop 'Windows — Aftrap'
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $inst 'bouw-installer.ps1') -Variant generiek
if ($LASTEXITCODE -ne 0) { throw 'Aftrap-installer mislukt' }

Kop 'Mac — De Vierkante Paal'
& py (Join-Path $inst 'mac\bouw-mac.py')
if ($LASTEXITCODE -ne 0) { throw 'DVP Mac-build mislukt' }

Kop 'Mac — Aftrap'
& py (Join-Path $inst 'mac\bouw-mac.py') --variant generiek
if ($LASTEXITCODE -ne 0) { throw 'Aftrap Mac-build mislukt' }

Kop 'Klaar'
Get-ChildItem $uit -File | Where-Object { $_.Extension -in '.exe', '.zip' } |
    Sort-Object Name |
    Format-Table Name, @{n = 'MB'; e = { [math]::Round($_.Length / 1MB, 1) } }, LastWriteTime -AutoSize
Write-Host "Alles staat in  $uit"
Write-Host "Deel .exe + LEESMIJ-redactie.txt / .zip + LEESMIJ-mac.txt"
