param(
    [switch]$Yes,
    [switch]$ForceEnv,
    [int]$Port = 18890,
    [string]$Trigger = 'gemma',
    [string]$Model = 'gemma4:e2b',
    [int]$ContextSize = 4096,
    [double]$Temperature = 0.2,
    [string]$McVersion = '1.20.4',
    [bool]$PlayitEnabled = $false,
    [string]$PlayitUrl = '',
    [string]$AdminUser = '',
    [string]$AdminPass = ''
)

$ErrorActionPreference = 'Stop'

$BootstrapZipUrl = if ([string]::IsNullOrWhiteSpace($env:ARX_BOOTSTRAP_ZIP_URL)) { 'https://arxmc.studio/arx-runtime.zip' } else { $env:ARX_BOOTSTRAP_ZIP_URL }
$BootstrapChecksumsUrl = if ([string]::IsNullOrWhiteSpace($env:ARX_BOOTSTRAP_CHECKSUMS_URL)) { 'https://arxmc.studio/checksums.txt' } else { $env:ARX_BOOTSTRAP_CHECKSUMS_URL }
$BootstrapInstallDir = if ([string]::IsNullOrWhiteSpace($env:ARX_INSTALL_DIR)) { Join-Path $env:USERPROFILE 'ARX' } else { $env:ARX_INSTALL_DIR }
$ScriptDir = if ([string]::IsNullOrWhiteSpace($PSScriptRoot)) { (Get-Location).Path } else { $PSScriptRoot }
if (-not (Test-Path $ScriptDir)) { $ScriptDir = (Get-Location).Path }

function Get-BootstrapExpectedHash([string]$ChecksumsText, [string]$TargetFileName) {
    foreach ($rawLine in ($ChecksumsText -split "`n")) {
        $line = $rawLine.Trim()
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith('#')) { continue }
        $m = [regex]::Match($line, '^(?<hash>[a-fA-F0-9]{64})\s+\*?(?<name>.+)$')
        if (-not $m.Success) { continue }
        if ($m.Groups['name'].Value.Trim() -eq $TargetFileName) {
            return $m.Groups['hash'].Value.ToLowerInvariant()
        }
    }
    return ''
}

function Assert-BootstrapZipIntegrity([string]$ZipPath, [string]$ZipUrl, [string]$ChecksumsUrl) {
    $checksums = Invoke-RestMethod -Uri $ChecksumsUrl
    if ($checksums -isnot [string]) { $checksums = [string]$checksums }

    $targetFile = [System.IO.Path]::GetFileName(([System.Uri]$ZipUrl).AbsolutePath)
    if ([string]::IsNullOrWhiteSpace($targetFile)) {
        throw "Unable to determine target filename from bootstrap URL: $ZipUrl"
    }

    $expected = Get-BootstrapExpectedHash -ChecksumsText $checksums -TargetFileName $targetFile
    if ([string]::IsNullOrWhiteSpace($expected)) {
        throw "Missing checksum entry for $targetFile in $ChecksumsUrl"
    }

    $actual = (Get-FileHash -Path $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        throw "Bootstrap checksum mismatch for $targetFile. Expected $expected but got $actual"
    }
}

function Test-ProjectRoot([string]$BaseDir) {
    return (Test-Path (Join-Path $BaseDir 'requirements.txt')) -and
           (Test-Path (Join-Path $BaseDir 'scripts\generate_env.py')) -and
           (Test-Path (Join-Path $BaseDir 'install.ps1'))
}

if (-not (Test-ProjectRoot $ScriptDir)) {
    Write-Host "[ARX] Bootstrap mode detected. Downloading runtime bundle..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Force -Path $BootstrapInstallDir | Out-Null

    $zipPath = Join-Path ([System.IO.Path]::GetTempPath()) ("arx-runtime-{0}.zip" -f ([Guid]::NewGuid().ToString('N')))
    try {
        Invoke-WebRequest -Uri $BootstrapZipUrl -OutFile $zipPath
        Assert-BootstrapZipIntegrity -ZipPath $zipPath -ZipUrl $BootstrapZipUrl -ChecksumsUrl $BootstrapChecksumsUrl
        Expand-Archive -Path $zipPath -DestinationPath $BootstrapInstallDir -Force
    }
    finally {
        Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
    }

    $reentry = Join-Path $BootstrapInstallDir 'install.ps1'
    if (-not (Test-Path $reentry)) {
        $nested = Get-ChildItem -Path $BootstrapInstallDir -Filter install.ps1 -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($nested) { $reentry = $nested.FullName }
    }
    if (-not (Test-Path $reentry)) {
        throw "Bootstrap failed: install.ps1 not found after extracting $BootstrapZipUrl"
    }

    Write-Host "[ARX] Re-launching installer from $reentry" -ForegroundColor Cyan
    $reentryArgs = @{
        Yes = $Yes
        ForceEnv = $ForceEnv
        Port = $Port
        Trigger = $Trigger
        Model = $Model
        ContextSize = $ContextSize
        Temperature = $Temperature
        McVersion = $McVersion
        PlayitEnabled = $PlayitEnabled
        PlayitUrl = $PlayitUrl
        AdminUser = $AdminUser
        AdminPass = $AdminPass
    }
    & $reentry @reentryArgs
    exit $LASTEXITCODE
}

Set-Location -Path $ScriptDir

function Test-InteractiveConsole {
    try {
        return [Environment]::UserInteractive -and -not [Console]::IsInputRedirected -and -not [Console]::IsOutputRedirected
    } catch {
        return $false
    }
}

$script:CanUseFancyUi = Test-InteractiveConsole

function Test-UnicodeSupport {
    $forceAscii = if ($env:ARX_FORCE_ASCII) { [string]$env:ARX_FORCE_ASCII } else { '' }
    if ($forceAscii.Trim().ToLowerInvariant() -in @('1', 'true', 'yes', 'on')) {
        return $false
    }

    try {
        $encName = [Console]::OutputEncoding.WebName
        if ($encName -and $encName.ToLowerInvariant().Contains('utf')) {
            return $true
        }
    } catch {
    }

    $langHint = if ($env:LC_ALL) { [string]$env:LC_ALL } elseif ($env:LANG) { [string]$env:LANG } else { '' }
    return $langHint.Trim().ToLowerInvariant().Contains('utf')
}

function Get-StateStyle {
    $statePath = Join-Path $ScriptDir 'state\arx_ui.json'
    if (-not (Test-Path $statePath)) {
        return ''
    }

    try {
        $raw = Get-Content -Path $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($raw -and $raw.style) {
            return ([string]$raw.style).Trim().ToLowerInvariant()
        }
    } catch {
    }

    return ''
}

function Resolve-InstallerStyle {
    # Allowed styles: underground, classic, dos, minimal, off
    $style = ''
    if (-not [string]::IsNullOrWhiteSpace($env:ARX_STYLE)) {
        $style = $env:ARX_STYLE
    }
    if ([string]::IsNullOrWhiteSpace($style)) {
        $style = Get-StateStyle
    }

    $style = ([string]$style).Trim().ToLowerInvariant()
    if ($style -notin @('underground', 'classic', 'dos', 'minimal', 'off')) {
        $style = 'underground'
    }

    if ($style -in @('underground', 'classic') -and -not (Test-UnicodeSupport)) {
        return 'minimal'
    }

    return $style
}

$script:InstallerStyle = Resolve-InstallerStyle

function Safe-Clear {
    if ($script:CanUseFancyUi) {
        try { Clear-Host } catch { }
    }
}

function Get-BannerLines {
    switch ($script:InstallerStyle) {
        'underground' {
            # Isometric-flavored ARX logo -- ASCII-safe for PS 5.1.
            # Full Unicode version lives in scripts/ui/ascii_assets.py.
            return @(
                '       _/_/_/    _/_/_/    _/      _/',
                '      _/    _/  _/    _/    _/  _/',
                '     _/_/_/_/  _/_/_/        _/',
                '    _/    _/  _/    _/      _/',
                '   _/    _/  _/    _/      _/',
                '',
                '   >> Agentic Runtime for eXecution <<'
            )
        }
        'classic' {
            # Legacy style (pre-overhaul).
            return @(
                '    ___    ____  _  __',
                '   /   |  / __ \| |/ /',
                '  / /| | / /_/ /   /',
                ' / ___ |/ _, _/   |',
                '/_/  |_/_/ |_/_/|_|'
            )
        }
        'dos' {
            return @(
                '______   ______  __   __',
                '|  _  \ /  __  \ \ \ / /',
                '| | | | | /  \ |  \ V /',
                '| | | | | |  | |   > <',
                '| |/ /  | \__/ |  / . \',
                '|___/    \____/  /_/ \_\'
            )
        }
        'minimal' {
            return @(
                '   _   ___ __  __',
                '  /_\ | _ \\ \/ /',
                ' / _ \|   / >  <',
                '/_/ \_\_|_\/_/\_\'
            )
        }
        'off' {
            return @()
        }
        default {
            return @(
                '       _/_/_/    _/_/_/    _/      _/',
                '      _/    _/  _/    _/    _/  _/',
                '     _/_/_/_/  _/_/_/        _/',
                '    _/    _/  _/    _/      _/',
                '   _/    _/  _/    _/      _/',
                '',
                '   >> Agentic Runtime for eXecution <<'
            )
        }
    }
}

# ---------------------------------------------------------------------------
#  Themed color palette -- consistent cyan/white hierarchy, no rainbow.
# ---------------------------------------------------------------------------
$script:C_LOGO   = 'Cyan'
$script:C_ACCENT = 'DarkCyan'
$script:C_CHROME = 'DarkGray'
$script:C_TEXT   = 'White'
$script:C_OK     = 'Green'
$script:C_WARN   = 'Yellow'

function Show-Banner {
    Safe-Clear
    Write-Host ''
    $lines = Get-BannerLines
    if ($lines.Count -gt 0) {
        foreach ($line in $lines) {
            Write-Host $line -ForegroundColor $script:C_LOGO
        }
        Write-Host ''
    }
    Write-Host '  .-------------------------------------------------------.' -ForegroundColor $script:C_CHROME
    Write-Host '  |  A R X   //  Production Setup                         |' -ForegroundColor $script:C_TEXT
    Write-Host "  '-------------------------------------------------------'" -ForegroundColor $script:C_CHROME
    Write-Host ''
}

function Show-TitleAnimation {
    if ($Yes -or -not $script:CanUseFancyUi) { return }

    $lines = Get-BannerLines
    if ($lines.Count -eq 0) { return }

    $maxLen = ($lines | ForEach-Object { $_.Length } | Measure-Object -Maximum).Maximum

    for ($col = 1; $col -le $maxLen; $col += 3) {
        Clear-Host
        Write-Host ''
        for ($i = 0; $i -lt $lines.Count; $i++) {
            $line = $lines[$i]
            $n = [Math]::Min($col, $line.Length)
            $left = $line.Substring(0, $n)
            $pad = ' ' * ($maxLen - $n)
            Write-Host ($left + $pad) -ForegroundColor $script:C_LOGO
        }
        Write-Host ''
        Write-Host '  .-------------------------------------------------------.' -ForegroundColor $script:C_CHROME
        Write-Host '  |  A R X   //  Production Setup                         |' -ForegroundColor $script:C_TEXT
        Write-Host "  '-------------------------------------------------------'" -ForegroundColor $script:C_CHROME
        Start-Sleep -Milliseconds 25
    }
}

function Show-Transition([string]$Text) {
    if ($Yes) {
        Write-Host "  [ARX] $Text" -ForegroundColor $script:C_ACCENT
        return
    }
    foreach ($d in @('.', '..', '...')) {
        Write-Host "`r  [ARX] $Text$d   " -ForegroundColor $script:C_ACCENT -NoNewline
        Start-Sleep -Milliseconds 90
    }
    Write-Host ''
}

function Show-IntroAnim {
    if ($Yes -or -not $script:CanUseFancyUi) { return }
    $width = 40
    $stages = @(4, 10, 16, 22, 28, 34, 40)
    foreach ($fill in $stages) {
        $bar = ('=' * $fill) + (' ' * ($width - $fill))
        $pct = [int](($fill / $width) * 100)
        Write-Host ("`r  Initializing  [{0}]  {1,3}%" -f $bar, $pct) -ForegroundColor $script:C_ACCENT -NoNewline
        Start-Sleep -Milliseconds 55
    }
    Write-Host ''
}

function Show-Box([string]$Title) {
    Write-Host ''
    Write-Host "  .--- $Title " -ForegroundColor $script:C_CHROME -NoNewline
    $pad = 56 - $Title.Length
    if ($pad -lt 1) { $pad = 1 }
    Write-Host ('-' * $pad + '.') -ForegroundColor $script:C_CHROME
}

function Show-AsciiDivider([string]$Tag) {
    $label = switch ($Tag) {
        'port'    { 'NETWORK' }
        'trigger' { 'AI AGENT' }
        'model'   { 'MODEL' }
        'ctx'     { 'CONTEXT' }
        'temp'    { 'TEMPERATURE' }
        'admin'   { 'CREDENTIALS' }
        default   { 'CONFIGURE' }
    }
    Write-Host "  |  $label" -ForegroundColor $script:C_ACCENT
    Write-Host ''
}

function Select-FromList(
    [string]$Title,
    [string[]]$Options,
    [int]$DefaultIndex = 0,
    [string]$ArtTag = 'default',
    [string]$Hint = 'Use Up/Down arrows and Enter to choose.'
) {
    if (-not $script:CanUseFancyUi) {
        Show-Banner
        Show-Box $Title
        Show-AsciiDivider $ArtTag
        Write-Host "  $Hint" -ForegroundColor $script:C_CHROME
        for ($i = 0; $i -lt $Options.Count; $i++) {
            Write-Host ("    [{0}] {1}" -f ($i + 1), $Options[$i]) -ForegroundColor $script:C_TEXT
        }
        while ($true) {
            $raw = Read-Host ("Choose 1-{0} (default {1})" -f $Options.Count, ($DefaultIndex + 1))
            if (-not $raw) { return $Options[$DefaultIndex] }
            if ($raw -match '^\d+$') {
                $pick = [int]$raw
                if ($pick -ge 1 -and $pick -le $Options.Count) {
                    return $Options[$pick - 1]
                }
            }
            Write-Host 'Invalid selection, try again.' -ForegroundColor Yellow
        }
    }

    $index = $DefaultIndex

    while ($true) {
        Safe-Clear
        Show-Banner
        Show-Box $Title
        Show-AsciiDivider $ArtTag
        Write-Host "  $Hint" -ForegroundColor $script:C_CHROME
        Write-Host ''

        for ($i=0; $i -lt $Options.Count; $i++) {
            if ($i -eq $index) {
                Write-Host ("    > {0}" -f $Options[$i]) -ForegroundColor Black -BackgroundColor Cyan
            } else {
                Write-Host ("      {0}" -f $Options[$i]) -ForegroundColor $script:C_TEXT
            }
        }

        try {
            $key = [System.Console]::ReadKey($true)
        } catch {
            $raw = Read-Host ("Choose 1-{0} (default {1})" -f $Options.Count, ($index + 1))
            if (-not $raw) { return $Options[$index] }
            if ($raw -match '^\d+$') {
                $pick = [int]$raw
                if ($pick -ge 1 -and $pick -le $Options.Count) {
                    return $Options[$pick - 1]
                }
            }
            continue
        }

        switch ($key.Key) {
            'UpArrow' {
                $index--
                if ($index -lt 0) { $index = $Options.Count - 1 }
            }
            'DownArrow' {
                $index++
                if ($index -ge $Options.Count) { $index = 0 }
            }
            'Enter' {
                return $Options[$index]
            }
            default {
            }
        }
    }
}

function Prompt-TextWithArt([string]$Title, [string]$ArtTag, [string]$PromptText) {
    if ($script:CanUseFancyUi) {
        Show-Banner
        Show-Box $Title
    }
    Show-AsciiDivider $ArtTag
    return Read-Host $PromptText
}

function Step([int]$Index, [int]$Total, [string]$Name, [scriptblock]$Action) {
    $bar = '=' * $Index + '-' * ($Total - $Index)
    Write-Host ("  [{0}] [{1}/{2}] {3}" -f $bar, $Index, $Total, $Name) -ForegroundColor $script:C_ACCENT
    & $Action
    Write-Host ("  [{0}] {1}" -f '+', $Name) -ForegroundColor $script:C_OK
}

function Require-Command([string]$Name, [string]$Hint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw $Hint
    }
}

function Test-JavaRuntime([int]$Min = 21) {
    $info = Get-JavaVersionInfo
    return ([int]$info.major -ge $Min)
}

function Get-JavaVersionInfo {
    $result = @{
        major = 0
        firstLine = ''
        source = ''
        path = ''
    }

    $candidates = New-Object 'System.Collections.Generic.List[string]'

    # 1) Commands from current PATH (collect all, not just first)
    try {
        $cmds = Get-Command java -All -ErrorAction SilentlyContinue
        foreach ($cmd in $cmds) {
            $src = if ($cmd.Source) { $cmd.Source } elseif ($cmd.Path) { $cmd.Path } else { '' }
            if ($src) { [void]$candidates.Add([string]$src) }
        }
    } catch {
    }

    # 2) JAVA_HOME
    if ($env:JAVA_HOME) {
        $jh = Join-Path $env:JAVA_HOME 'bin\java.exe'
        if (Test-Path $jh) { [void]$candidates.Add($jh) }
    }

    # 3) Registry-discovered Java homes
    $regRoots = @(
        'HKLM:\SOFTWARE\JavaSoft\JDK',
        'HKLM:\SOFTWARE\JavaSoft\JRE',
        'HKLM:\SOFTWARE\WOW6432Node\JavaSoft\JDK',
        'HKLM:\SOFTWARE\WOW6432Node\JavaSoft\JRE',
        'HKLM:\SOFTWARE\Eclipse Adoptium\JDK',
        'HKLM:\SOFTWARE\Eclipse Adoptium\JRE',
        'HKLM:\SOFTWARE\Microsoft\JDK'
    )
    foreach ($root in $regRoots) {
        if (-not (Test-Path $root)) { continue }

        try {
            $cv = (Get-ItemProperty -Path $root -ErrorAction SilentlyContinue).CurrentVersion
            if ($cv) {
                $cvPath = Join-Path $root $cv
                $home = (Get-ItemProperty -Path $cvPath -ErrorAction SilentlyContinue).JavaHome
                if ($home) {
                    $jp = Join-Path $home 'bin\java.exe'
                    if (Test-Path $jp) { [void]$candidates.Add($jp) }
                }
            }
        } catch {
        }

        try {
            $subs = Get-ChildItem -Path $root -ErrorAction SilentlyContinue
            foreach ($sub in $subs) {
                $home = (Get-ItemProperty -Path $sub.PSPath -ErrorAction SilentlyContinue).JavaHome
                if ($home) {
                    $jp = Join-Path $home 'bin\java.exe'
                    if (Test-Path $jp) { [void]$candidates.Add($jp) }
                }
            }
        } catch {
        }
    }

    # 4) Common install roots
    $possible = @(
        "$env:ProgramFiles\Java",
        "$env:ProgramFiles\Eclipse Adoptium",
        "$env:ProgramFiles\Microsoft",
        "$env:ProgramFiles\Amazon Corretto",
        "${env:ProgramFiles(x86)}\Java",
        "${env:ProgramFiles(x86)}\Eclipse Adoptium"
    )
    foreach ($root in $possible) {
        if (-not $root -or -not (Test-Path $root)) { continue }
        try {
            $found = Get-ChildItem -Path $root -Recurse -Filter java.exe -ErrorAction SilentlyContinue |
                Where-Object { $_.FullName -match '\\bin\\java\.exe$' }
            foreach ($item in $found) {
                [void]$candidates.Add($item.FullName)
            }
        } catch {
        }
    }

    # Deduplicate + verify existence
    $seen = @{}
    $unique = @()
    foreach ($p in $candidates) {
        if (-not $p) { continue }
        try {
            if (-not (Test-Path $p)) { continue }
            $full = [System.IO.Path]::GetFullPath($p)
            $key = $full.ToLowerInvariant()
            if (-not $seen.ContainsKey($key)) {
                $seen[$key] = $true
                $unique += $full
            }
        } catch {
        }
    }

    foreach ($javaPath in $unique) {
        $major = 0
        $line = ''
        $src = ''

        try {
            # java -version writes to stderr, which produces ErrorRecords.
            # Under $ErrorActionPreference='Stop' that throws before we can
            # read the output.  Temporarily lower to 'Continue' so the
            # 2>&1 redirect works as intended.
            $prevEAP = $ErrorActionPreference
            $ErrorActionPreference = 'Continue'
            $vline = (& $javaPath -version 2>&1 | Select-Object -First 1)
            $ErrorActionPreference = $prevEAP
            if ($vline) {
                $s = [string]$vline
                $line = $s
                $src = 'java -version'
                if ($s -match 'version "1\.(\d+)') { $major = [int]$Matches[1] }
                elseif ($s -match 'version "(\d+)') { $major = [int]$Matches[1] }
                elseif ($s -match '^(?:openjdk|java)\s+(\d+)') { $major = [int]$Matches[1] }
            }

            if ($major -eq 0) {
                $ErrorActionPreference = 'Continue'
                $vline2 = (& $javaPath --version 2>&1 | Select-Object -First 1)
                $ErrorActionPreference = $prevEAP
                if ($vline2) {
                    $s2 = [string]$vline2
                    $line = $s2
                    $src = 'java --version'
                    if ($s2 -match '^(?:openjdk|java)\s+(\d+)') { $major = [int]$Matches[1] }
                    elseif ($s2 -match '\b(\d+)\.\d+') { $major = [int]$Matches[1] }
                }
            }
        } catch {
            $ErrorActionPreference = $prevEAP
        }

        if ($major -gt [int]$result.major) {
            $result.major = $major
            $result.firstLine = $line
            $result.source = $src
            $result.path = $javaPath
        }
    }

    return $result
}

function Get-JavaMajorVersion {
    return (Get-JavaVersionInfo).major
}

function Test-IsElevated {
    try {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($identity)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch {
        return $false
    }
}

function Invoke-WingetInstallPackage {
    param(
        [string]$PackageId,
        [int]$TimeoutSec = 900
    )

    $isElevated = Test-IsElevated
    $scope = if ($isElevated) { 'machine' } else { 'user' }

    $args = @(
        'install',
        '--id', $PackageId,
        '-e',
        '--scope', $scope,
        '--accept-package-agreements',
        '--accept-source-agreements',
        '--disable-interactivity',
        '--silent'
    )

    $safeId = ($PackageId -replace '[^A-Za-z0-9_.-]', '_')
    $logPath = Join-Path ([System.IO.Path]::GetTempPath()) ("arx-winget-{0}-{1}.log" -f $safeId, ([Guid]::NewGuid().ToString('N')))

    Write-Host ("[ARX] winget install {0} (scope={1})..." -f $PackageId, $scope) -ForegroundColor DarkGray
    Write-Host "[ARX] Waiting for winget response. If Windows prompts for admin approval, accept the UAC dialog." -ForegroundColor DarkGray

    try {
        $proc = Start-Process -FilePath 'winget' -ArgumentList $args -NoNewWindow -PassThru -RedirectStandardOutput $logPath -RedirectStandardError $logPath
    } catch {
        return @{
            code = 1
            timedOut = $false
            output = @($_.Exception.Message)
            scope = $scope
        }
    }

    $elapsed = 0
    $tick = 3
    $lastPrintedLineCount = 0
    $printedUacHint = $false
    while (-not $proc.HasExited -and $elapsed -lt $TimeoutSec) {
        Start-Sleep -Seconds $tick
        $elapsed += $tick

        if (Test-Path $logPath) {
            try {
                $allLines = @(Get-Content -Path $logPath -ErrorAction SilentlyContinue)
                if ($allLines.Count -gt $lastPrintedLineCount) {
                    $newLines = $allLines[$lastPrintedLineCount..($allLines.Count - 1)]
                    foreach ($line in $newLines) {
                        $s = [string]$line
                        if (-not [string]::IsNullOrWhiteSpace($s)) {
                            Write-Host ("[winget] {0}" -f $s.Trim()) -ForegroundColor DarkGray
                        }
                    }
                    $lastPrintedLineCount = $allLines.Count
                }
            } catch {
            }
        }

        if (($elapsed -ge 18) -and (-not $printedUacHint)) {
            Write-Host "[ARX] Still waiting - check for a hidden UAC/admin popup and approve it." -ForegroundColor Yellow
            $printedUacHint = $true
        }

        if (($elapsed % 15) -eq 0) {
            Write-Host ("[ARX] winget still running for {0}s..." -f $elapsed) -ForegroundColor DarkGray
        }
    }

    $timedOut = $false
    if (-not $proc.HasExited) {
        $timedOut = $true
        try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
    }

    $lines = @()
    try {
        $lines = Get-Content -Path $logPath -ErrorAction SilentlyContinue | ForEach-Object { [string]$_ }
    } catch {
        $lines = @()
    } finally {
        Remove-Item $logPath -Force -ErrorAction SilentlyContinue
    }

    return @{
        code = $(if ($timedOut) { 124 } else { $proc.ExitCode })
        timedOut = $timedOut
        output = $lines
        scope = $scope
    }
}

function Ensure-Java {
    $min = 21
    $info = Get-JavaVersionInfo
    $major = [int]$info.major
    if ($major -ge $min) {
        $src = if ($info.source) { $info.source } else { 'java' }
        $line = if ($info.firstLine) { $info.firstLine } else { 'version output unavailable' }
        $jpath = if ($info.path) { $info.path } else { 'java (PATH)' }
        Write-Host "Java 21+ detected via $src (major=$major) - skipping install." -ForegroundColor DarkGray
        Write-Host ("  Java: {0}" -f $line) -ForegroundColor DarkGray
        Write-Host ("  Path: {0}" -f $jpath) -ForegroundColor DarkGray
        return
    }

    # PATH might not be refreshed in current shell; try refreshing once before install.
    $env:PATH = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'User')
    $info = Get-JavaVersionInfo
    $major = [int]$info.major
    if ($major -ge $min) {
        $src = if ($info.source) { $info.source } else { 'java' }
        $line = if ($info.firstLine) { $info.firstLine } else { 'version output unavailable' }
        $jpath = if ($info.path) { $info.path } else { 'java (PATH)' }
        Write-Host "Java 21+ detected via $src after PATH refresh (major=$major) - skipping install." -ForegroundColor DarkGray
        Write-Host ("  Java: {0}" -f $line) -ForegroundColor DarkGray
        Write-Host ("  Path: {0}" -f $jpath) -ForegroundColor DarkGray
        return
    }

    Write-Host "Java $min+ required. Attempting install/upgrade via winget..." -ForegroundColor Yellow
    Ensure-WingetForWindows

    if (-not (Test-IsElevated)) {
        Write-Host "PowerShell is not running as Administrator. Winget may fail for machine-scoped Java packages." -ForegroundColor Yellow
        Write-Host "If Java install fails, re-run this installer in an Administrator PowerShell." -ForegroundColor Yellow
    }

    $packages = @(
        'Microsoft.OpenJDK.21',
        'EclipseAdoptium.Temurin.21.JRE',
        'EclipseAdoptium.Temurin.21.JDK'
    )

    $installed = $false
    $wingetIndicatesPresent = $false
    $timedOutAny = $false

    foreach ($pkg in $packages) {
        $attempt = Invoke-WingetInstallPackage -PackageId $pkg -TimeoutSec 900
        $wingetOutput = @($attempt.output)
        $code = [int]$attempt.code
        if ($attempt.timedOut) {
            $timedOutAny = $true
            Write-Host ("winget timed out while installing {0}. Trying next package id..." -f $pkg) -ForegroundColor Yellow
            continue
        }

        $text = ($wingetOutput -join "`n")
        if ($text -match 'Successfully installed' -or
            $text -match 'Found an existing package already installed' -or
            $text -match 'No newer package versions are available') {
            $wingetIndicatesPresent = $true
        }

        if ($code -eq 0) {
            $installed = $true
        } else {
            if ($text -match 'requires administrator privileges' -or
                $text -match '0x8a15000f' -or
                $text -match 'Access is denied') {
                Write-Host "winget reported admin privilege requirement for Java package installation." -ForegroundColor Yellow
            }
        }

        $env:PATH = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'User')
        $info = Get-JavaVersionInfo
        $major = [int]$info.major
        if ($major -ge $min) {
            $jpath = if ($info.path) { $info.path } else { 'java (PATH)' }
            Write-Host "Java runtime ready (major=$major)." -ForegroundColor DarkGray
            Write-Host ("  Path: {0}" -f $jpath) -ForegroundColor DarkGray
            return
        }
    }

    # Final check after attempting all package IDs.
    $env:PATH = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'User')
    $info = Get-JavaVersionInfo
    $major = [int]$info.major
    if ($major -ge $min) {
        $jpath = if ($info.path) { $info.path } else { 'java (PATH)' }
        Write-Host "Java runtime ready (major=$major)." -ForegroundColor DarkGray
        Write-Host ("  Path: {0}" -f $jpath) -ForegroundColor DarkGray
        return
    }

    if ($wingetIndicatesPresent -or $installed) {
        Write-Host "Java 21 package appears installed but version probe failed in this shell." -ForegroundColor Yellow
        Write-Host "Continuing setup. If server start later reports old Java, open a new terminal and rerun installer." -ForegroundColor Yellow
        return
    }

    if ($timedOutAny) {
        throw 'winget Java install timed out. Re-run installer in Administrator PowerShell, or install Java 21+ manually and rerun.'
    }

    if (-not (Test-IsElevated)) {
        throw 'Could not install Java automatically in non-elevated shell. Re-run PowerShell as Administrator and rerun installer.'
    }

    throw 'Could not install Java automatically. Install Java 21+ manually and rerun installer.'
}

function Ensure-WingetForWindows {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'winget not found. Install App Installer from Microsoft Store, then rerun installer.'
    }
}

function Ensure-Ollama([string]$ModelName) {
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Write-Host 'Ollama not found. Attempting install via winget...' -ForegroundColor Yellow
        Ensure-WingetForWindows
        $attempt = Invoke-WingetInstallPackage -PackageId 'Ollama.Ollama' -TimeoutSec 900
        $text = (($attempt.output | ForEach-Object { [string]$_ }) -join "`n")
        if ($attempt.timedOut) {
            throw 'winget timed out while installing Ollama. Re-run in Administrator PowerShell or install manually from https://ollama.com/download/windows'
        }
        if (($attempt.code -ne 0) -and
            ($text -notmatch 'Found an existing package already installed') -and
            ($text -notmatch 'No newer package versions are available')) {
            throw 'Failed to install Ollama automatically. Install manually: https://ollama.com/download/windows'
        }
    }

    try {
        Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 | Out-Null
    } catch {
        Write-Host 'Starting Ollama in background...' -ForegroundColor Yellow
        Start-Process -WindowStyle Hidden -FilePath 'ollama' -ArgumentList 'serve'
        Start-Sleep -Seconds 3
    }

    try {
        Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 6 | Out-Null
    } catch {
        throw 'Ollama API not reachable on localhost:11434. Start Ollama and rerun.'
    }

    & ollama pull $ModelName
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to pull model $ModelName"
    }
}

function Download-ServerJar {
    $jarPath = Join-Path $ScriptDir 'app/minecraft_server/server.jar'
    if (Test-Path $jarPath) { return }

    $manifest = Invoke-RestMethod 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'
    $version = $manifest.versions | Where-Object { $_.id -eq $McVersion } | Select-Object -First 1
    if (-not $version) { throw "Could not resolve Minecraft version '$McVersion'." }

    $meta = Invoke-RestMethod $version.url
    Invoke-WebRequest $meta.downloads.server.url -OutFile $jarPath
}

function Validate-Inputs {
    if ($Port -lt 1024 -or $Port -gt 65535) { throw 'Port must be between 1024 and 65535.' }
    if ($Trigger -notmatch '^[a-zA-Z0-9_-]{2,24}$') { throw 'Trigger must match [a-zA-Z0-9_-]{2,24}.' }
    if ($Model -notmatch ':') { throw 'Model should look like name:tag (example: gemma4:e2b).' }
    if ($ContextSize -lt 1024 -or $ContextSize -gt 32768) { throw 'Context size must be between 1024 and 32768.' }
    if ($Temperature -lt 0 -or $Temperature -gt 2) { throw 'Temperature must be between 0 and 2.' }
    if ($McVersion -notmatch '^[0-9]+\.[0-9]+(\.[0-9]+)?$') { throw 'Minecraft version must look like 1.20.4.' }
    if ($AdminUser -notmatch '^[a-zA-Z0-9_.-]{3,32}$') { throw 'Admin username must match [a-zA-Z0-9_.-]{3,32}.' }
    if ([string]::IsNullOrWhiteSpace($AdminPass)) { throw 'Admin password is required.' }
    if ($AdminPass.Length -lt 8) { throw 'Admin password must be at least 8 characters.' }
}

function Ensure-Playit {
    if (-not $PlayitEnabled) { return }

    if (-not (Get-Command playit -ErrorAction SilentlyContinue)) {
        Write-Host 'Playit not found. Attempting install via winget...' -ForegroundColor Yellow
        Ensure-WingetForWindows
        $attempt = Invoke-WingetInstallPackage -PackageId 'DevelopedMethods.playit' -TimeoutSec 900
        $text = (($attempt.output | ForEach-Object { [string]$_ }) -join "`n")
        if ($attempt.timedOut) {
            throw 'winget timed out while installing Playit. Re-run in Administrator PowerShell or install manually: https://playit.gg/download'
        }
        if (($attempt.code -ne 0) -and
            ($text -notmatch 'Found an existing package already installed') -and
            ($text -notmatch 'No newer package versions are available')) {
            throw 'Failed to install Playit automatically. Install manually: https://playit.gg/download'
        }
    }

    Write-Host 'Playit enabled. Complete tunnel claim after install using: arx tunnel setup' -ForegroundColor Yellow
}

function Install-ArxLauncher {
    $targetDir = Join-Path $env:USERPROFILE 'AppData\Local\Microsoft\WindowsApps'
    if (-not (Test-Path $targetDir)) {
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    }

    $pythonPath = Join-Path $ScriptDir '.venv\Scripts\python.exe'
    $cliPath = Join-Path $ScriptDir 'scripts\arx_cli.py'
    if (-not (Test-Path $pythonPath)) { throw '.venv\Scripts\python.exe not found.' }
    if (-not (Test-Path $cliPath)) { throw 'scripts\arx_cli.py not found.' }

    $launcherLines = @(
        '@echo off',
        'setlocal',
        "set \"ARX_PY=$pythonPath\"",
        "set \"ARX_CLI=$cliPath\"",
        'if not exist "%ARX_PY%" (',
        '  echo [ARX][ERROR] Python runtime not found: %ARX_PY%',
        '  exit /b 1',
        ')',
        'if not exist "%ARX_CLI%" (',
        '  echo [ARX][ERROR] CLI script not found: %ARX_CLI%',
        '  exit /b 1',
        ')',
        '"%ARX_PY%" "%ARX_CLI%" %*'
    )
    Set-Content -Path (Join-Path $targetDir 'arx.bat') -Value ($launcherLines -join "`r`n") -Encoding ASCII
}

try {
    Show-TitleAnimation
    Show-Banner
    Show-IntroAnim
    Show-Transition 'Opening setup'
    Show-Box 'Interactive First-Run'

    if (-not $Yes) {
        $inPort = Prompt-TextWithArt -Title 'Dashboard Port' -ArtTag 'port' -PromptText "Dashboard port [$Port]"
        if ($inPort) { $Port = [int]$inPort }

        $inTrig = Prompt-TextWithArt -Title 'Trigger Word' -ArtTag 'trigger' -PromptText "Agent trigger word [$Trigger]"
        if ($inTrig) { $Trigger = $inTrig }

        $Model = Select-FromList -Title 'Choose Gemma model' -Options @('gemma4:e2b','gemma3:latest','gemma2:9b') -DefaultIndex 0 -ArtTag 'model' -Hint 'Select with Up/Down and press Enter.'

        # Context size is no longer an interactive setup prompt.
        # Keep default at 4096 for reliability; advanced users can tune later.

        $Temperature = [double](Select-FromList -Title 'Choose temperature' -Options @('0.1','0.2','0.3','0.5','0.7') -DefaultIndex 1 -ArtTag 'temp' -Hint 'Lower = stricter, higher = more creative.')

        $playitChoice = Select-FromList -Title 'Public Internet Access' -Options @('false (LAN only)','true (use Playit tunnel)') -DefaultIndex 0 -ArtTag 'default' -Hint 'Enable Playit tunnel setup for internet players?'
        $PlayitEnabled = $playitChoice.StartsWith('true')
        if ($PlayitEnabled -and [string]::IsNullOrWhiteSpace($PlayitUrl)) {
            $PlayitUrl = Prompt-TextWithArt -Title 'Playit URL' -ArtTag 'default' -PromptText 'Optional existing Playit public URL (leave blank to set up later)'
        }

        if ([string]::IsNullOrWhiteSpace($AdminUser)) {
            $AdminUser = Prompt-TextWithArt -Title 'Admin Account' -ArtTag 'admin' -PromptText 'Admin username [admin]'
            if ([string]::IsNullOrWhiteSpace($AdminUser)) { $AdminUser = 'admin' }
        }
        if ([string]::IsNullOrWhiteSpace($AdminPass)) {
            if (-not [string]::IsNullOrWhiteSpace($env:ARX_ADMIN_PASS)) {
                $AdminPass = $env:ARX_ADMIN_PASS
            }
            if ([string]::IsNullOrWhiteSpace($AdminPass)) {
                $AdminPass = Prompt-TextWithArt -Title 'Admin Account' -ArtTag 'admin' -PromptText 'Admin password (required, min 8 chars)'
            }
        }
    } else {
        if ([string]::IsNullOrWhiteSpace($AdminUser)) { $AdminUser = 'admin' }
        if ([string]::IsNullOrWhiteSpace($AdminPass) -and -not [string]::IsNullOrWhiteSpace($env:ARX_ADMIN_PASS)) {
            $AdminPass = $env:ARX_ADMIN_PASS
        }
    }

    # Context is fixed by default for setup stability.
    if (-not $PSBoundParameters.ContainsKey('ContextSize')) { $ContextSize = 4096 }

    Validate-Inputs

    Show-Banner
    Show-Box 'Setup Summary'
    Write-Host "    Platform         : windows" -ForegroundColor $script:C_TEXT
    Write-Host "    Dashboard port   : $Port" -ForegroundColor $script:C_TEXT
    Write-Host "    Trigger          : $Trigger" -ForegroundColor $script:C_TEXT
    Write-Host "    Gemma model      : $Model" -ForegroundColor $script:C_TEXT
    Write-Host "    Temperature      : $Temperature" -ForegroundColor $script:C_TEXT
    Write-Host "    Minecraft ver    : $McVersion" -ForegroundColor $script:C_TEXT
    Write-Host "    Playit enabled   : $PlayitEnabled" -ForegroundColor $script:C_TEXT
    if ($PlayitUrl) { Write-Host "    Playit URL       : $PlayitUrl" -ForegroundColor $script:C_TEXT }
    Write-Host "    Admin user       : $AdminUser" -ForegroundColor $script:C_TEXT

    Show-Transition 'Running installation pipeline'

    $step = 0; $total = 11

    Step (++$step) $total 'Prerequisite checks' {
        Require-Command python 'Python 3.11+ is required'
    }

    Step (++$step) $total 'Java runtime readiness' {
        Ensure-Java
    }

    Step (++$step) $total 'Python environment' {
        if (-not (Test-Path .venv)) { & python -m venv .venv }
        & .\.venv\Scripts\python -m pip install --upgrade pip
    }

    Step (++$step) $total 'Dependency install' {
        & .\.venv\Scripts\python -m pip install -r requirements.txt
    }

    Step (++$step) $total 'Ollama readiness' {
        Ensure-Ollama -ModelName $Model
    }

    Step (++$step) $total 'Playit tunnel readiness' {
        Ensure-Playit
    }

    Step (++$step) $total 'Project directories' {
        New-Item -ItemType Directory -Force -Path 'app/minecraft_server/logs' | Out-Null
        New-Item -ItemType Directory -Force -Path 'state' | Out-Null
    }

    Step (++$step) $total 'Minecraft server jar' {
        Download-ServerJar
    }

    Step (++$step) $total 'Secure env generation' {
        if ((Test-Path .env) -and (-not $ForceEnv)) {
            Write-Host '.env already exists. Keeping current values. Use --force-env to regenerate.' -ForegroundColor Yellow
        } else {
            $env:ARX_BIND_HOST = '127.0.0.1'
            $env:ARX_BIND_PORT = "$Port"
            $env:ARX_ADMIN_USER = "$AdminUser"
            $env:ARX_ADMIN_PASS = "$AdminPass"
            $env:ARX_TRIGGER = "$Trigger"
            $env:ARX_MODEL = "$Model"
            $env:ARX_CONTEXT_SIZE = "$ContextSize"
            $env:ARX_TEMPERATURE = "$Temperature"
            $env:ARX_PLAYIT_ENABLED = ($(if($PlayitEnabled){'true'}else{'false'}))
            $env:ARX_PLAYIT_URL = "$PlayitUrl"
            & .\.venv\Scripts\python scripts\generate_env.py --output .env
        }
    }

    Step (++$step) $total 'Runtime setup profile' {
        $cfg = @{
            setup_completed = $true
            agent_trigger = $Trigger
            gemma_model = $Model
            gemma_context_size = 4096
            gemma_temperature = $Temperature
            gemma_max_reply_chars = 220
            gemma_cooldown_sec = 2.5
            playit_enabled = $PlayitEnabled
            playit_url = $PlayitUrl
        }
        $cfg | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 state/arx_config.json
    }

    Step (++$step) $total 'ARX launcher install' {
        Install-ArxLauncher
    }

    Show-Box 'Install Complete'
    Write-Host ''
    Write-Host "    Dashboard URL : http://localhost:$Port/" -ForegroundColor $script:C_OK
    Write-Host "    Start command : arx start" -ForegroundColor $script:C_TEXT
    Write-Host "    Help command  : arx help" -ForegroundColor $script:C_TEXT
    Write-Host "    Status        : arx status" -ForegroundColor $script:C_TEXT
    Write-Host "    Shutdown      : arx shutdown" -ForegroundColor $script:C_TEXT
    Write-Host "    Tunnel setup  : arx tunnel setup" -ForegroundColor $script:C_TEXT
    Write-Host "    Tunnel status : arx tunnel status" -ForegroundColor $script:C_TEXT
    Write-Host "    AI context    : arx ai set-context 4096" -ForegroundColor $script:C_TEXT
    Write-Host "    Launcher      : $env:USERPROFILE\AppData\Local\Microsoft\WindowsApps\arx.bat" -ForegroundColor $script:C_CHROME
    Write-Host "    Gemma trigger : $Trigger" -ForegroundColor $script:C_ACCENT
    Write-Host ''
    Show-Transition 'All done'
    exit 0
}
catch {
    Write-Host ("[ARX][ERROR] {0}" -f $_.Exception.Message) -ForegroundColor Red
    exit 1
}
