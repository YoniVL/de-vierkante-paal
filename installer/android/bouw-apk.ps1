# =====================================================================
#  Android-APK's bouwen (De Vierkante Paal + Aftrap)
#
#  Draai:  powershell -ExecutionPolicy Bypass -File installer\android\bouw-apk.ps1
#
#  Nodig op de bouw-pc:
#   - Android SDK (via Android Studio), met ANDROID_HOME gezet
#   - JDK 17 (Temurin) -- het script zoekt 'm onder Program Files
#   - Python 3.12 (los, voor Chaquopy) -- winget install Python.Python.3.12
#   - internet (de eerste keer; Gradle/Chaquopy downloaden veel)
#
#  Resultaat:  installer\uit\De Vierkante Paal.apk  en  Aftrap.apk
# =====================================================================
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$uit = Join-Path (Split-Path -Parent $here) 'uit'
New-Item -ItemType Directory -Path $uit -Force | Out-Null

function Stap($t) { Write-Host "`n=== $t ===" -ForegroundColor Cyan }

# --- JDK 17 zoeken -------------------------------------------------
Stap 'JDK 17'
$jdk = Get-ChildItem 'C:\Program Files\Eclipse Adoptium\jdk-17*' -Directory -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending | Select-Object -First 1
if (-not $jdk) {
    $jdk = Get-ChildItem 'C:\Program Files\*\jdk-17*', 'C:\Program Files\Java\jdk-17*' -Directory -ErrorAction SilentlyContinue |
        Select-Object -First 1
}
if (-not $jdk) { throw "Geen JDK 17 gevonden. Installeer Temurin 17 van adoptium.net." }
$env:JAVA_HOME = $jdk.FullName
Write-Host "  JAVA_HOME = $env:JAVA_HOME"

# --- SDK controleren --------------------------------------------
Stap 'Android SDK'
if (-not $env:ANDROID_HOME) {
    $guess = Join-Path $env:LOCALAPPDATA 'Android\Sdk'
    if (Test-Path $guess) { $env:ANDROID_HOME = $guess }
}
if (-not $env:ANDROID_HOME -or -not (Test-Path $env:ANDROID_HOME)) {
    throw "ANDROID_HOME niet gezet / SDK niet gevonden."
}
Write-Host "  ANDROID_HOME = $env:ANDROID_HOME"

# --- bouwen -----------------------------------------------------
Stap 'Gradle: assembleDvpRelease + assembleAftrapRelease'
$cache = Join-Path $env:USERPROFILE 'dvp-android-build\.cache'
Push-Location $here
try {
    & .\gradlew.bat clean assembleDvpRelease assembleAftrapRelease `
        --no-daemon --console=plain --project-cache-dir="$cache"
    if ($LASTEXITCODE -ne 0) { throw "Gradle-build mislukt (exit $LASTEXITCODE)" }
} finally { Pop-Location }

# --- APK's ophalen --------------------------------------------
Stap 'APK''s kopiëren naar installer\uit'
$outBase = Join-Path $env:USERPROFILE 'dvp-android-build\app\outputs\apk'
$paren = @(
    @{ src = "$outBase\dvp\release\app-dvp-release.apk";       dst = 'De Vierkante Paal.apk' }
    @{ src = "$outBase\aftrap\release\app-aftrap-release.apk"; dst = 'Aftrap.apk' }
)
foreach ($p in $paren) {
    if (-not (Test-Path $p.src)) { throw "APK niet gevonden: $($p.src)" }
    Copy-Item $p.src (Join-Path $uit $p.dst) -Force
    $mb = [math]::Round((Get-Item $p.src).Length / 1MB, 1)
    Write-Host "  $($p.dst)  ($mb MB)"
}

Write-Host "`nKLAAR. De .apk's staan in $uit" -ForegroundColor Green
Write-Host "Deel ze via Drive/WeTransfer; op de telefoon: tik de APK, sta 'onbekende bron' toe."
