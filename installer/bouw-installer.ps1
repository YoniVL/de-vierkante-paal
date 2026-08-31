# =====================================================================
#  De Vierkante Paal - installatiepakket bouwen
#
#  Draai dit EEN keer op je eigen pc om het deelbestand te maken:
#      powershell -ExecutionPolicy Bypass -File installer\bouw-installer.ps1
#
#  Resultaat: installer\uit\Installeer De Vierkante Paal.exe
#  (dat bestand deel je met de redactieleden, bv. via WeTransfer/Drive)
#
#  Nodig op de bouw-pc: internet (eenmalig), Python (py of python in PATH),
#  en iexpress.exe (staat standaard in C:\Windows\System32).
# =====================================================================
param(
    [ValidateSet('dvp', 'generiek')]
    [string]$Variant = 'dvp',
    [string]$PythonZip = '',
    [string]$Uit = ''
)
$ErrorActionPreference = 'Stop'

$APPNAAM = if ($Variant -eq 'generiek') { 'Aftrap' } else { 'De Vierkante Paal' }

$PYVER = '3.12.8'
$PYURL = "https://www.python.org/ftp/python/$PYVER/python-$PYVER-embed-amd64.zip"

$inst    = $PSScriptRoot
$proj    = Split-Path -Parent $inst
$cache   = Join-Path $inst 'cache'
$build   = Join-Path $inst 'build'
$payload = Join-Path $build 'payload'
if (-not $Uit) { $Uit = Join-Path $inst 'uit' }

Add-Type -AssemblyName System.IO.Compression.FileSystem

function Stap($t) { Write-Host "`n=== $t ===" -ForegroundColor Cyan }

# --- 0. schoon ------------------------------------------------------
Stap '0/9  Opruimen'
if (Test-Path $build) { Remove-Item $build -Recurse -Force }
New-Item -ItemType Directory -Path $payload, $cache, $Uit -Force | Out-Null

# --- 1. embeddable Python ophalen ---------------------------------
Stap '1/9  Embeddable Python'
if (-not $PythonZip) { $PythonZip = Join-Path $cache "python-$PYVER-embed-amd64.zip" }
if (-not (Test-Path $PythonZip)) {
    Write-Host "  downloaden van python.org ..."
    Invoke-WebRequest -Uri $PYURL -OutFile $PythonZip
}
Write-Host "  gebruik: $PythonZip"
$py = Join-Path $payload 'python'
[System.IO.Compression.ZipFile]::ExtractToDirectory($PythonZip, $py)

# --- 2. ._pth patchen (site-packages + import site) --------------
Stap '2/9  python._pth aanpassen'
$pth = Get-ChildItem $py -Filter 'python*._pth' | Select-Object -First 1
$zipnaam = (Get-ChildItem $py -Filter 'python*.zip' | Select-Object -First 1).Name
# ".." = de installatiemap zelf, zodat "import dvp" werkt ongeacht de werkmap
@"
$zipnaam
.
..
Lib\site-packages

import site
"@ | Set-Content -Path $pth.FullName -Encoding ASCII
Write-Host "  $($pth.Name) bijgewerkt"

# --- 3. dependencies cross-installeren voor cp312/win_amd64 -----
Stap '3/9  Dependencies (curl_cffi, bs4, lxml, jinja2, pillow)'
$pyCmd = if (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python' }
$sp = Join-Path $py 'Lib\site-packages'
New-Item -ItemType Directory -Path $sp -Force | Out-Null
& $pyCmd -m pip install --target $sp `
    --python-version 3.12 --implementation cp --platform win_amd64 `
    --abi cp312 --abi abi3 --abi none `
    --only-binary=:all: --no-compile `
    -r (Join-Path $proj 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'pip install is mislukt' }

# --- 4. app-broncode kopieren ----------------------------------
Stap '4/9  App-broncode kopieren'
$dst = Join-Path $payload 'dvp'
robocopy (Join-Path $proj 'dvp') $dst /E /XD __pycache__ /XF '*.pyc' /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw 'robocopy is mislukt' }

# --- 5. versie.txt + uninstall.ps1 + merk (variant) ----------
Stap "5/9  versie.txt + variant ($Variant)"
$versie = Get-Date -Format 'yyyy.MM.dd'
Set-Content -Path (Join-Path $payload 'versie.txt') -Value $versie -Encoding ASCII
Copy-Item (Join-Path $inst 'uninstall.ps1') (Join-Path $payload 'uninstall.ps1')
if ($Variant -eq 'generiek') {
    '{ "app_naam": "Aftrap", "toon_kiezer": true, "whoscored": false, "vaste_ploeg": null, "poort": 8757, "accent": "#20c063", "accent_diep": "#17a552" }' |
        Set-Content -Path (Join-Path $payload 'merk.json') -Encoding ASCII
    Copy-Item (Join-Path $inst 'assets\aftrap-logo.png') (Join-Path $dst 'static\logo.png') -Force
    Write-Host "  merk.json + Aftrap-logo"
}
Write-Host "  versie $versie"

# --- 6. logo.ico genereren met de gebouwde Python -------------
Stap '6/9  logo.ico genereren'
Push-Location $payload
try {
    & (Join-Path $py 'python.exe') -m dvp.assets
} finally { Pop-Location }
if (Test-Path (Join-Path $dst 'static\logo.ico')) {
    Write-Host '  logo.ico ok'
} else {
    Write-Warning '  logo.ico niet aangemaakt - de wizard probeert het opnieuw op de doel-pc'
}

# --- 7. payload -> zip -----------------------------------------
Stap '7/9  Pakket inpakken'
$zip = Join-Path $build 'dvp-pakket.zip'
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $payload, $zip, [System.IO.Compression.CompressionLevel]::Optimal, $false)
$logoPng = Join-Path $dst 'static\logo.png'   # in de payload (evt. het Aftrap-logo)
$logoIco = Join-Path $dst 'static\logo.ico'
$zipMB = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host "  dvp-pakket.zip = $zipMB MB"

# --- 8. zelf-uitpakkende stub compileren ---------------------
# We gebruiken de C#-compiler die bij .NET Framework 4 hoort (staat op elke
# Windows 10/11) - geen externe tools nodig, en het resultaat is een echte .exe
# met icoon die het pakket uitpakt en de wizard start.
Stap '8/9  Zelf-uitpakker compileren'
$csc = Get-ChildItem "$env:windir\Microsoft.NET\Framework64\v*\csc.exe" |
    Sort-Object FullName -Descending | Select-Object -First 1
if (-not $csc) { throw 'csc.exe (.NET Framework 4) niet gevonden' }
$exe = Join-Path $Uit "Installeer $APPNAAM.exe"
if (Test-Path $exe) { Remove-Item $exe -Force }
$cscArgs = @(
    '/nologo', '/target:winexe', '/platform:anycpu', '/optimize+',
    "/out:$exe",
    "/win32icon:$logoIco",
    '/reference:System.Windows.Forms.dll',
    "/resource:$zip,res.dvp-pakket.zip",
    "/resource:$(Join-Path $inst 'installeer.ps1'),res.installeer.ps1",
    "/resource:$logoPng,res.logo.png",
    (Join-Path $inst 'sfx.cs')
)
& $csc.FullName @cscArgs
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $exe)) { throw 'compileren van de stub is mislukt' }

# --- 9. afronden --------------------------------------------
Stap '9/9  Afronden'
if ($Variant -eq 'dvp') {
    Copy-Item (Join-Path $inst 'LEESMIJ-redactie.txt') $Uit -Force
}
$exeMB = [math]::Round((Get-Item $exe).Length / 1MB, 1)

Write-Host "`nKLAAR." -ForegroundColor Green
Write-Host "Deelbestand: $exe  ($exeMB MB)"
