# =====================================================================
#  De Vierkante Paal - installatiewizard
#  Draait op de pc van een redactielid. Wordt gestart door _setup.bat
#  nadat het zelf-uitpakkende pakket zijn bestanden in %TEMP% heeft gezet.
# =====================================================================

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$PORT      = 8756
$HIER      = Split-Path -Parent $MyInvocation.MyCommand.Path
$ZIP       = Join-Path $HIER 'dvp-pakket.zip'
$LOGO      = Join-Path $HIER 'logo.png'

# App-naam + poort + versie uit het pakket lezen (merk.json / versie.txt in de zip)
$APPNAAM = 'De Vierkante Paal'
$script:versieNieuw = ''
if (Test-Path $ZIP) {
    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $z = [System.IO.Compression.ZipFile]::OpenRead($ZIP)
        foreach ($naam in 'merk.json', 'versie.txt') {
            $e = $z.Entries | Where-Object { $_.FullName -eq $naam } | Select-Object -First 1
            if (-not $e) { continue }
            $sr = New-Object System.IO.StreamReader($e.Open())
            $inhoud = $sr.ReadToEnd(); $sr.Close()
            if ($naam -eq 'merk.json') {
                try {
                    $m = $inhoud | ConvertFrom-Json
                    if ($m.app_naam) { $APPNAAM = $m.app_naam }
                    if ($m.poort)    { $PORT = [int]$m.poort }
                } catch { }
            } else {
                $script:versieNieuw = $inhoud.Trim()
            }
        }
        $z.Dispose()
    } catch { }
}
$REGID  = ($APPNAAM -replace '[^A-Za-z0-9]', '')
$REGKEY = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$REGID"

# --- kleuren -------------------------------------------------------------
$cBg    = [System.Drawing.Color]::FromArgb(14, 16, 20)
$cVlak  = [System.Drawing.Color]::FromArgb(23, 26, 33)
$cInkt  = [System.Drawing.Color]::FromArgb(231, 233, 238)
$cGrijs = [System.Drawing.Color]::FromArgb(138, 147, 163)
$cRood  = [System.Drawing.Color]::FromArgb(255, 77, 103)
$cGoed  = [System.Drawing.Color]::FromArgb(74, 222, 128)
$cSlecht= [System.Drawing.Color]::FromArgb(248, 113, 113)

# --- helpers -----------------------------------------------------------
function Test-PoortInGebruik([int]$p) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $c.Connect('127.0.0.1', $p); $c.Close(); return $true
    } catch { return $false }
}

function Get-BestaandeVersie([string]$map) {
    $vf = Join-Path $map 'versie.txt'
    if (Test-Path (Join-Path $map 'dvp\__init__.py')) {
        if (Test-Path $vf) { return (Get-Content $vf -Raw).Trim() }
        return '?'
    }
    return $null
}

function Test-Schrijfbaar([string]$map) {
    try {
        $ouder = Split-Path -Parent $map
        if (-not (Test-Path $ouder)) { $ouder = $map }
        if (-not (Test-Path $ouder)) { New-Item -ItemType Directory -Path $ouder -Force | Out-Null }
        $t = Join-Path $ouder ([System.IO.Path]::GetRandomFileName())
        [System.IO.File]::WriteAllText($t, 'x'); Remove-Item $t -Force
        return $true
    } catch { return $false }
}

function Is-BeschermdePad([string]$map) {
    $m = $map.ToLower()
    return ($m.StartsWith($env:windir.ToLower()) -or
            $m.StartsWith(([Environment]::GetFolderPath('ProgramFiles')).ToLower()) -or
            $m.StartsWith(([Environment]::GetFolderPath('ProgramFilesX86')).ToLower()))
}

# =====================================================================
#  FORM
# =====================================================================
$form = New-Object System.Windows.Forms.Form
$form.Text = "$APPNAAM - installeren"
$form.Size = New-Object System.Drawing.Size(600, 470)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.BackColor = $cBg
$form.Font = New-Object System.Drawing.Font('Segoe UI', 9.5)
$form.ForeColor = $cInkt

# --- kop --------------------------------------------------------------
$kop = New-Object System.Windows.Forms.Panel
$kop.Dock = 'Top'; $kop.Height = 66; $kop.BackColor = $cVlak
$form.Controls.Add($kop)

if (Test-Path $LOGO) {
    try {
        $pb = New-Object System.Windows.Forms.PictureBox
        $pb.Image = [System.Drawing.Image]::FromFile($LOGO)
        $pb.SizeMode = 'Zoom'; $pb.Size = New-Object System.Drawing.Size(46, 46)
        $pb.Location = New-Object System.Drawing.Point(12, 10)
        $kop.Controls.Add($pb)
    } catch { }
}
$kopTitel = New-Object System.Windows.Forms.Label
$kopTitel.Text = $APPNAAM
$kopTitel.Font = New-Object System.Drawing.Font('Segoe UI', 14, [System.Drawing.FontStyle]::Bold)
$kopTitel.ForeColor = $cRood
$kopTitel.AutoSize = $true
$kopTitel.Location = New-Object System.Drawing.Point(70, 12)
$kop.Controls.Add($kopTitel)
$kopSub = New-Object System.Windows.Forms.Label
$kopSub.Text = 'voorbereidingstool voor de podcast'
$kopSub.ForeColor = $cGrijs; $kopSub.AutoSize = $true
$kopSub.Location = New-Object System.Drawing.Point(72, 38)
$kop.Controls.Add($kopSub)

# --- voet met knoppen ------------------------------------------------
$voet = New-Object System.Windows.Forms.Panel
$voet.Dock = 'Bottom'; $voet.Height = 52; $voet.BackColor = $cVlak
$form.Controls.Add($voet)

$btnTerug = New-Object System.Windows.Forms.Button
$btnTerug.Text = 'Terug'; $btnTerug.Size = New-Object System.Drawing.Size(90, 30)
$btnTerug.Location = New-Object System.Drawing.Point(300, 11)
$btnTerug.FlatStyle = 'Flat'; $btnTerug.ForeColor = $cInkt
$voet.Controls.Add($btnTerug)

$btnVolgende = New-Object System.Windows.Forms.Button
$btnVolgende.Text = 'Volgende'; $btnVolgende.Size = New-Object System.Drawing.Size(110, 30)
$btnVolgende.Location = New-Object System.Drawing.Point(398, 11)
$btnVolgende.FlatStyle = 'Flat'; $btnVolgende.BackColor = $cRood
$btnVolgende.ForeColor = [System.Drawing.Color]::White
$voet.Controls.Add($btnVolgende)

$btnAnnuleer = New-Object System.Windows.Forms.Button
$btnAnnuleer.Text = 'Annuleren'; $btnAnnuleer.Size = New-Object System.Drawing.Size(90, 30)
$btnAnnuleer.Location = New-Object System.Drawing.Point(12, 11)
$btnAnnuleer.FlatStyle = 'Flat'; $btnAnnuleer.ForeColor = $cGrijs
$voet.Controls.Add($btnAnnuleer)

# --- inhoud ---------------------------------------------------------
$body = New-Object System.Windows.Forms.Panel
$body.Dock = 'Fill'; $body.Padding = New-Object System.Windows.Forms.Padding(18)
$form.Controls.Add($body)
$body.BringToFront()

# ---- paneel 1: checks --------------------------------------------
$p1 = New-Object System.Windows.Forms.Panel
$p1.Dock = 'Fill'
$l1 = New-Object System.Windows.Forms.Label
$l1.Text = "Deze wizard installeert $APPNAAM op deze pc. Python en alle onderdelen zitten in het pakket - je hoeft zelf niets te installeren."
$l1.AutoSize = $false; $l1.Dock = 'Top'; $l1.Height = 46
$p1.Controls.Add($l1)
$checkHost = New-Object System.Windows.Forms.FlowLayoutPanel
$checkHost.Dock = 'Fill'; $checkHost.FlowDirection = 'TopDown'
$checkHost.WrapContents = $false; $checkHost.Padding = New-Object System.Windows.Forms.Padding(0, 10, 0, 0)
$p1.Controls.Add($checkHost)
$checkHost.BringToFront()
$body.Controls.Add($p1)

function Voeg-CheckRij([string]$tekst, [bool]$ok, [string]$extra) {
    $r = New-Object System.Windows.Forms.Label
    $mark = if ($ok) { [char]0x2713 } else { [char]0x2717 }
    $r.Text = "  $mark   $tekst" + $(if ($extra) { "  -  $extra" } else { '' })
    $r.ForeColor = if ($ok) { $cGoed } else { $cSlecht }
    $r.AutoSize = $true; $r.Margin = New-Object System.Windows.Forms.Padding(0, 4, 0, 4)
    $r.Font = New-Object System.Drawing.Font('Segoe UI', 10)
    $checkHost.Controls.Add($r)
}

$script:checksOk = $true
function Herbouw-Checks {
    $checkHost.Controls.Clear()
    $script:checksOk = $true

    $b64 = [Environment]::Is64BitOperatingSystem
    Voeg-CheckRij '64-bit Windows' $b64 $(if (-not $b64) { 'vereist' } else { '' })
    if (-not $b64) { $script:checksOk = $false }

    $w10 = ([Environment]::OSVersion.Version.Major -ge 10)
    Voeg-CheckRij 'Windows 10 of nieuwer' $w10 $(if (-not $w10) { 'vereist' } else { '' })
    if (-not $w10) { $script:checksOk = $false }

    Voeg-CheckRij 'Python en onderdelen' $true 'meegeleverd in dit pakket'

    $zipOk = Test-Path $ZIP
    Voeg-CheckRij 'Installatiepakket compleet' $zipOk $(if (-not $zipOk) { 'dvp-pakket.zip ontbreekt' } else { '' })
    if (-not $zipOk) { $script:checksOk = $false }

    try { $vrijGB = [math]::Round(((Get-PSDrive -Name ($env:SystemDrive[0])).Free) / 1GB, 1) } catch { $vrijGB = 99 }
    $genoeg = $vrijGB -ge 0.3
    Voeg-CheckRij 'Vrije schijfruimte' $genoeg "$vrijGB GB vrij (ca. 200 MB nodig)"
    if (-not $genoeg) { $script:checksOk = $false }

    $poortVrij = -not (Test-PoortInGebruik $PORT)
    Voeg-CheckRij "Poort $PORT vrij" $poortVrij $(if (-not $poortVrij) { "$APPNAAM draait mogelijk al - dat is geen probleem" } else { '' })

    if ($script:versieNieuw) {
        $r = New-Object System.Windows.Forms.Label
        $r.Text = "      Versie in dit pakket: $script:versieNieuw"
        $r.ForeColor = $cGrijs; $r.AutoSize = $true
        $r.Margin = New-Object System.Windows.Forms.Padding(0, 12, 0, 0)
        $checkHost.Controls.Add($r)
    }
}

# ---- paneel 2: map + opties -------------------------------------
$p2 = New-Object System.Windows.Forms.Panel
$p2.Dock = 'Fill'; $p2.Visible = $false
$l2 = New-Object System.Windows.Forms.Label
$l2.Text = 'Kies waar de tool geinstalleerd wordt:'
$l2.AutoSize = $true; $l2.Location = New-Object System.Drawing.Point(0, 4)
$p2.Controls.Add($l2)

$txtMap = New-Object System.Windows.Forms.TextBox
$txtMap.Size = New-Object System.Drawing.Size(430, 24)
$txtMap.Location = New-Object System.Drawing.Point(0, 30)
$txtMap.BackColor = $cVlak; $txtMap.ForeColor = $cInkt; $txtMap.BorderStyle = 'FixedSingle'
$txtMap.Text = Join-Path ([Environment]::GetFolderPath('MyDocuments')) $APPNAAM
$p2.Controls.Add($txtMap)

$btnBladeren = New-Object System.Windows.Forms.Button
$btnBladeren.Text = 'Bladeren...'; $btnBladeren.Size = New-Object System.Drawing.Size(100, 24)
$btnBladeren.Location = New-Object System.Drawing.Point(440, 30)
$btnBladeren.FlatStyle = 'Flat'; $btnBladeren.ForeColor = $cInkt
$p2.Controls.Add($btnBladeren)

$lblMapInfo = New-Object System.Windows.Forms.Label
$lblMapInfo.AutoSize = $false; $lblMapInfo.Size = New-Object System.Drawing.Size(540, 40)
$lblMapInfo.Location = New-Object System.Drawing.Point(0, 60)
$lblMapInfo.ForeColor = $cGrijs
$p2.Controls.Add($lblMapInfo)

$chkBureaublad = New-Object System.Windows.Forms.CheckBox
$chkBureaublad.Text = 'Snelkoppeling op het bureaublad'
$chkBureaublad.Checked = $true; $chkBureaublad.AutoSize = $true
$chkBureaublad.Location = New-Object System.Drawing.Point(0, 110)
$p2.Controls.Add($chkBureaublad)

$chkStartup = New-Object System.Windows.Forms.CheckBox
$chkStartup.Text = 'Automatisch meestarten met Windows (draait onzichtbaar op de achtergrond)'
$chkStartup.AutoSize = $true
$chkStartup.Location = New-Object System.Drawing.Point(0, 138)
$p2.Controls.Add($chkStartup)

$chkData = New-Object System.Windows.Forms.CheckBox
$chkData.Text = 'Nu meteen een eerste keer de data ophalen (ca. 20 seconden, internet nodig)'
$chkData.Checked = $true; $chkData.AutoSize = $true
$chkData.Location = New-Object System.Drawing.Point(0, 166)
$p2.Controls.Add($chkData)
$body.Controls.Add($p2)

function Werk-MapInfo-Bij {
    $doel = $txtMap.Text.Trim()
    if (-not $doel) { $lblMapInfo.Text = ''; return $false }
    if (Is-BeschermdePad $doel) {
        $lblMapInfo.ForeColor = $cSlecht
        $lblMapInfo.Text = 'Kies geen map onder Program Files of Windows - daar kan de tool geen gegevens bewaren.'
        return $false
    }
    if (-not (Test-Schrijfbaar $doel)) {
        $lblMapInfo.ForeColor = $cSlecht
        $lblMapInfo.Text = 'Deze map kan niet beschreven worden. Kies een andere.'
        return $false
    }
    $bestaat = Get-BestaandeVersie $doel
    if ($bestaat) {
        $lblMapInfo.ForeColor = $cGrijs
        $lblMapInfo.Text = "Er staat al een installatie (versie $bestaat). Die wordt bijgewerkt naar $script:versieNieuw; je bewaarde afleveringen en data blijven behouden."
    } else {
        $lblMapInfo.ForeColor = $cGrijs
        $lblMapInfo.Text = "De tool komt in: $doel"
    }
    return $true
}

# ---- paneel 3: installeren -------------------------------------
$p3 = New-Object System.Windows.Forms.Panel
$p3.Dock = 'Fill'; $p3.Visible = $false
$lblDoen = New-Object System.Windows.Forms.Label
$lblDoen.Text = 'Bezig met installeren...'
$lblDoen.AutoSize = $true; $lblDoen.Location = New-Object System.Drawing.Point(0, 10)
$p3.Controls.Add($lblDoen)
$bar = New-Object System.Windows.Forms.ProgressBar
$bar.Size = New-Object System.Drawing.Size(540, 22)
$bar.Location = New-Object System.Drawing.Point(0, 40)
$bar.Style = 'Continuous'; $bar.Minimum = 0; $bar.Maximum = 100
$p3.Controls.Add($bar)
$logBox = New-Object System.Windows.Forms.TextBox
$logBox.Multiline = $true; $logBox.ReadOnly = $true; $logBox.ScrollBars = 'Vertical'
$logBox.Size = New-Object System.Drawing.Size(540, 210)
$logBox.Location = New-Object System.Drawing.Point(0, 76)
$logBox.BackColor = $cVlak; $logBox.ForeColor = $cGrijs; $logBox.BorderStyle = 'FixedSingle'
$p3.Controls.Add($logBox)
$body.Controls.Add($p3)

function Log([string]$t) {
    $logBox.AppendText($t + [Environment]::NewLine)
    [System.Windows.Forms.Application]::DoEvents()
}
function Stap([int]$pct, [string]$t) {
    $bar.Value = [math]::Min(100, $pct); $lblDoen.Text = $t; Log $t
}

# =====================================================================
#  navigatie
# =====================================================================
$script:stap = 1
function Toon-Stap([int]$n) {
    $script:stap = $n
    $p1.Visible = ($n -eq 1)
    $p2.Visible = ($n -eq 2)
    $p3.Visible = ($n -eq 3)
    $btnTerug.Enabled = ($n -eq 2)
    switch ($n) {
        1 { Herbouw-Checks; $btnVolgende.Text = 'Volgende'; $btnVolgende.Enabled = $script:checksOk }
        2 { Werk-MapInfo-Bij | Out-Null; $btnVolgende.Text = 'Installeren'; $btnVolgende.Enabled = $true }
        3 { $btnVolgende.Enabled = $false; $btnTerug.Enabled = $false; $btnAnnuleer.Enabled = $false }
    }
}

$txtMap.Add_TextChanged({ Werk-MapInfo-Bij | Out-Null })
$btnBladeren.Add_Click({
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    $dlg.Description = 'Kies de bovenliggende map'
    if ($dlg.ShowDialog() -eq 'OK') {
        $txtMap.Text = Join-Path $dlg.SelectedPath $APPNAAM
    }
})
$btnTerug.Add_Click({ Toon-Stap 1 })
$btnAnnuleer.Add_Click({ $form.Close() })

$btnVolgende.Add_Click({
    if ($script:stap -eq 1) { Toon-Stap 2; return }
    if ($script:stap -eq 2) {
        if (-not (Werk-MapInfo-Bij)) { return }
        Toon-Stap 3
        Voer-Installatie-Uit
        return
    }
    if ($script:stap -eq 3) {
        # 'Openen' / 'Sluiten'
        if ($btnVolgende.Tag -eq 'openen') {
            try { Start-Process (Join-Path $script:doel 'python\pythonw.exe') -ArgumentList 'dvp\launch.py' -WorkingDirectory $script:doel } catch { }
        }
        $form.Close()
    }
})

# =====================================================================
#  installatie
# =====================================================================
function Maak-Snelkoppeling([string]$lnkPad, [string]$doel) {
    $w = New-Object -ComObject WScript.Shell
    $s = $w.CreateShortcut($lnkPad)
    $s.TargetPath = Join-Path $doel 'python\pythonw.exe'
    $s.Arguments = '"dvp\launch.py"'
    $s.WorkingDirectory = $doel
    $ico = Join-Path $doel 'dvp\static\logo.ico'
    if (Test-Path $ico) { $s.IconLocation = $ico }
    $s.Description = $APPNAAM
    $s.Save()
}

function Voer-Installatie-Uit {
    $doel = $txtMap.Text.Trim()
    $script:doel = $doel
    try {
        Stap 5 'Map klaarzetten...'
        if (-not (Test-Path $doel)) { New-Item -ItemType Directory -Path $doel -Force | Out-Null }
        # een draaiende versie eerst stoppen (anders zit python.exe vast)
        try {
            (New-Object System.Net.WebClient).UploadString("http://127.0.0.1:$PORT/afsluiten", 'POST', '') | Out-Null
        } catch { }
        Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe' OR Name = 'python.exe'" |
            Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($doel) } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Milliseconds 600
        # bij een herinstallatie: alles weg behalve je eigen gegevens
        Get-ChildItem -LiteralPath $doel -Force |
            Where-Object { $_.Name -notin @('data', 'afleveringen') } |
            ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }

        Stap 20 'Bestanden uitpakken (dit duurt even)...'
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::ExtractToDirectory($ZIP, $doel)
        Stap 55 'Bestanden uitgepakt.'

        Stap 60 'Icoon klaarzetten...'
        if (-not (Test-Path (Join-Path $doel 'dvp\static\logo.ico'))) {
            try {
                Start-Process (Join-Path $doel 'python\python.exe') -ArgumentList '-m', 'dvp.assets' `
                    -WorkingDirectory $doel -Wait -WindowStyle Hidden
            } catch { Log "  (icoon overgeslagen: $_)" }
        }

        Stap 68 'Snelkoppelingen maken...'
        # altijd een zichtbare starter IN de installatiemap (zodat wie de map opent
        # meteen ziet hoe de tool start)
        Maak-Snelkoppeling (Join-Path $doel "$APPNAAM.lnk") $doel
        Log '  starter in de installatiemap gezet'
        # en in het menu Start (zo vind je 'm terug via de Windows-toets)
        try {
            Maak-Snelkoppeling (Join-Path ([Environment]::GetFolderPath('Programs')) "$APPNAAM.lnk") $doel
            Log '  toegevoegd aan het menu Start'
        } catch { Log "  (menu Start overgeslagen: $_)" }
        if ($chkBureaublad.Checked) {
            $desk = [Environment]::GetFolderPath('Desktop')
            Maak-Snelkoppeling (Join-Path $desk "$APPNAAM.lnk") $doel
            Log '  bureaublad-snelkoppeling gemaakt'
        }
        if ($chkStartup.Checked) {
            $su = [Environment]::GetFolderPath('Startup')
            Maak-Snelkoppeling (Join-Path $su "$APPNAAM.lnk") $doel
            Log '  meestarten met Windows ingesteld'
            # bij meestarten willen we niet dat de tool zich afsluit als een tabblad sluit
            try {
                Start-Process (Join-Path $doel 'python\python.exe') `
                    -ArgumentList '-c', "from dvp import store; store.init(); store.set_kv('settings:blijf_draaien', True)" `
                    -WorkingDirectory $doel -Wait -WindowStyle Hidden
            } catch { Log "  (achtergrond-instelling overgeslagen: $_)" }
        }

        Stap 74 'Registreren bij Windows...'
        try {
            New-Item -Path $REGKEY -Force | Out-Null
            Set-ItemProperty $REGKEY 'DisplayName'     $APPNAAM
            Set-ItemProperty $REGKEY 'DisplayVersion'  ($script:versieNieuw)
            Set-ItemProperty $REGKEY 'Publisher'       'De Vierkante Paal'
            Set-ItemProperty $REGKEY 'InstallLocation' $doel
            Set-ItemProperty $REGKEY 'DisplayIcon'     (Join-Path $doel 'dvp\static\logo.ico')
            Set-ItemProperty $REGKEY 'UninstallString' ("powershell -NoProfile -ExecutionPolicy Bypass -File `"" + (Join-Path $doel 'uninstall.ps1') + "`"")
            Set-ItemProperty $REGKEY 'NoModify' 1 -Type DWord
            Set-ItemProperty $REGKEY 'NoRepair' 1 -Type DWord
        } catch { Log "  (registratie overgeslagen: $_)" }

        if ($chkData.Checked) {
            Stap 82 'Eerste keer data ophalen (ca. 20 sec)...'
            try {
                Start-Process (Join-Path $doel 'python\python.exe') `
                    -ArgumentList '-c', "from dvp.app import _ververs; _ververs('all')" `
                    -WorkingDirectory $doel -Wait -WindowStyle Hidden
                Log '  data opgehaald'
            } catch { Log "  (ophalen overgeslagen - kan later in de tool: $_)" }
        }

        Stap 100 'Klaar!'
        $lblDoen.Text = "$APPNAAM is geinstalleerd."
        Log ''
        Log "Map: $doel"
        Log 'Je kan de tool starten via de snelkoppeling op je bureaublad.'
        Log 'Verwijderen kan via Windows > Instellingen > Apps.'
        $btnVolgende.Text = 'Openen'
        $btnVolgende.Tag = 'openen'
        $btnVolgende.Enabled = $true
        $btnAnnuleer.Text = 'Sluiten'
        $btnAnnuleer.Enabled = $true
    } catch {
        $bar.Style = 'Continuous'
        $lblDoen.ForeColor = $cSlecht
        $lblDoen.Text = 'Er ging iets mis tijdens de installatie.'
        Log ''
        Log "FOUT: $_"
        $btnAnnuleer.Text = 'Sluiten'
        $btnAnnuleer.Enabled = $true
    }
}

Toon-Stap 1
[void]$form.ShowDialog()
