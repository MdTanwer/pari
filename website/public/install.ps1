# PARI Installer for Windows (PowerShell)
# Usage: irm https://www.pari-cli.in/install.ps1 | iex
#
# This script installs the release that published it. Set
# $env:PARI_INSTALL_FROM_SOURCE = '1' to install that same tag from git.
#
# If running this script directly from a local file and encountering ExecutionPolicy errors:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#
# To uninstall:
#   Remove-Item -Recurse -Force "$env:USERPROFILE\.pari"
#   (and remove ~/.pari\venv\Scripts from your User Environment PATH)

$ErrorActionPreference = "Stop"

$Version = "0.1.7"
$Package = "pari-cli==$Version"
$SourceUrl = "git+https://github.com/MdTanwer/pari.git@v$Version"
if ($env:PARI_INSTALL_FROM_SOURCE -eq "1") {
    $Spec = $SourceUrl
} else {
    $Spec = $Package
}

function Show-InstallFailure {
    Write-Host "Error: failed to install $Spec." -ForegroundColor Red
    if ($env:PARI_INSTALL_FROM_SOURCE -ne "1") {
        Write-Host "PyPI did not provide pari-cli==$Version." -ForegroundColor Yellow
        Write-Host "Re-run with `$env:PARI_INSTALL_FROM_SOURCE = '1' to install tag v$Version." -ForegroundColor Yellow
    }
}

$InstallDir = Join-Path $env:USERPROFILE ".pari"
$VenvDir = Join-Path $InstallDir "venv"
$ScriptsDir = Join-Path $VenvDir "Scripts"

function Show-InstalledPari {
    param([string]$PreferredDir)
    if ($PreferredDir) {
        $parts = @($PreferredDir) + @(
            ($env:Path -split ';') | Where-Object { $_.Trim() -and $_.Trim() -ne $PreferredDir }
        )
        $env:Path = $parts -join ';'
    }
    $resolved = Get-Command pari-cli -ErrorAction SilentlyContinue
    if (-not $resolved) {
        Write-Host "pari-cli installed. Open a new terminal, then run: pari-cli --version" -ForegroundColor Yellow
        return
    }
    if ($PreferredDir) {
        $resolvedDir = Split-Path $resolved.Source -Parent
        if ($resolvedDir -ne $PreferredDir) {
            Write-Host "An older pari-cli is earlier on PATH: $($resolved.Source)" -ForegroundColor Yellow
            Write-Host "The updated copy is in $PreferredDir. Open a new terminal so that directory comes first." -ForegroundColor Yellow
        }
    }
    $version = $null
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $version = & $resolved.Source --version 2>$null | Select-Object -Last 1
    } catch {
        $version = $null
    }
    $ErrorActionPreference = $previous
    if ($version) {
        Write-Output $version
    } else {
        Write-Output "pari-cli installed"
    }
}

# 1. Prefer uv if available (fastest). --force installs this script's pin.
if (Get-Command uv -ErrorAction SilentlyContinue) {
    & uv tool install --force $Spec
    if ($LASTEXITCODE -ne 0) {
        Show-InstallFailure
        return
    }
    $binDir = (& uv tool dir --bin 2>$null | Select-Object -Last 1)
    if ($binDir) { $binDir = $binDir.Trim() }
    Show-InstalledPari $binDir
    return
}

# 2. Prefer pipx if available (isolated)
if (Get-Command pipx -ErrorAction SilentlyContinue) {
    & pipx install --force $Spec
    if ($LASTEXITCODE -ne 0) {
        Show-InstallFailure
        return
    }
    Show-InstalledPari
    return
}

# 3. Fallback: Find working Python >= 3.11 (skipping WindowsApps Microsoft Store stubs)
$candidates = @()

if (Get-Command py -ErrorAction SilentlyContinue) {
    $candidates += @{ Cmd = "py"; Args = @("-3") }
}

$allPy = Get-Command python -All -ErrorAction SilentlyContinue | Where-Object { $_.Source -notlike "*WindowsApps*" }
foreach ($p in $allPy) {
    $candidates += @{ Cmd = $p.Source; Args = @() }
}

$PythonCmd = $null
$PythonArgs = @()

foreach ($c in $candidates) {
    $ver = & $c.Cmd @($c.Args + @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}'); sys.exit(0 if sys.version_info >= (3, 11) else 1)")) 2>$null
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($ver)) {
        $PythonCmd = $c.Cmd
        $PythonArgs = $c.Args
        break
    }
}

if (-not $PythonCmd) {
    Write-Host "[-] Error: Python 3.11+ is required but no working interpreter was found." -ForegroundColor Red
    Write-Host "Please install Python from https://www.python.org/ or run: winget install Python.Python.3.11" -ForegroundColor Red
    return
}

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

# Clean existing venv if corrupt
if (Test-Path $VenvDir) {
    Remove-Item -Recurse -Force $VenvDir -ErrorAction SilentlyContinue
}

# Create venv
& $PythonCmd @($PythonArgs + @("-m", "venv", $VenvDir))
if ($LASTEXITCODE -ne 0) {
    Write-Host "[-] Error: Failed to create virtual environment in $VenvDir" -ForegroundColor Red
    return
}

$VenvPip = Join-Path $ScriptsDir "pip.exe"
& $VenvPip install --upgrade pip --quiet

& $VenvPip install $Spec
if ($LASTEXITCODE -ne 0) {
    Show-InstallFailure
    return
}

# Ensure Scripts directory is in user PATH (robust array contains check)
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$currentPaths = ($UserPath -split ';') | Where-Object { $_.Trim() }
if ($currentPaths -notcontains $ScriptsDir) {
    Write-Host "[+] Adding $ScriptsDir to User PATH..." -ForegroundColor Yellow
    $newPath = if ($UserPath) { "$UserPath;$ScriptsDir" } else { $ScriptsDir }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
}

# Always ensure ScriptsDir is in current session's PATH
$sessionPaths = ($env:Path -split ';') | Where-Object { $_.Trim() }
if ($sessionPaths -notcontains $ScriptsDir) {
    $env:Path = "$env:Path;$ScriptsDir"
}

# Verify binary resolution / check for shadowing
$resolved = Get-Command pari-cli -ErrorAction SilentlyContinue
if ($resolved) {
    $resolvedDir = Split-Path $resolved.Source -Parent
    if ($resolvedDir -ne $ScriptsDir) {
        Write-Host "[!] Note: 'pari-cli' command currently resolves to: $($resolved.Source)" -ForegroundColor Yellow
    }
}

Write-Output "pari-cli installed"
