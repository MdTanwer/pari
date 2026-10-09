# PARI Installer for Windows (PowerShell)
# Usage: irm https://pari-cli.in/install.ps1 | iex
# (Alternative: irm https://raw.githubusercontent.com/MdTanwer/pari/main/install.ps1 | iex)
#
# If running this script directly from a local file and encountering ExecutionPolicy errors:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#
# To uninstall:
#   Remove-Item -Recurse -Force "$env:USERPROFILE\.pari"
#   (and remove ~/.pari\venv\Scripts from your User Environment PATH)

$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/MdTanwer/pari.git"
$InstallDir = Join-Path $env:USERPROFILE ".pari"
$VenvDir = Join-Path $InstallDir "venv"
$ScriptsDir = Join-Path $VenvDir "Scripts"

Write-Host @"
  ___   _   ___ ___ 
 | _ \ /_\ | _ \_ _|
 |  _// _ \|   /| | 
 |_| /_/ \_\_|_\___|
"@ -ForegroundColor Cyan

Write-Host "Installing PARI — Terminal Coding Agent on Windows..." -ForegroundColor Green
Write-Host ""

# 1. Prefer uv if available (fastest)
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "[+] Found uv. Installing pari-cli via uv tool..." -ForegroundColor Green
    & uv tool install --force pari-cli
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[*] PyPI install failed; attempting fallback to GitHub repository..." -ForegroundColor Yellow
        & uv tool install --force "git+$RepoUrl"
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[-] Error: Installation via uv failed." -ForegroundColor Red
            return
        }
    }
    Write-Host "`n[✓] PARI installed successfully! Type 'pari-cli' to start." -ForegroundColor Cyan
    return
}

# 2. Prefer pipx if available (isolated)
if (Get-Command pipx -ErrorAction SilentlyContinue) {
    Write-Host "[+] Found pipx. Installing pari-cli via pipx..." -ForegroundColor Green
    & pipx install --force pari-cli
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[*] PyPI install failed; attempting fallback to GitHub repository..." -ForegroundColor Yellow
        & pipx install --force "git+$RepoUrl"
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[-] Error: Installation via pipx failed." -ForegroundColor Red
            return
        }
    }
    Write-Host "`n[✓] PARI installed successfully! Type 'pari-cli' to start." -ForegroundColor Cyan
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

Write-Host "[*] Setting up isolated environment in $VenvDir..." -ForegroundColor Yellow
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

# Install pari-cli with fallback
& $VenvPip install pari-cli
if ($LASTEXITCODE -ne 0) {
    Write-Host "[*] PyPI install failed; falling back to GitHub source..." -ForegroundColor Yellow
    & $VenvPip install "git+$RepoUrl"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[-] Error: Failed to install PARI via pip." -ForegroundColor Red
        return
    }
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

Write-Host "`n[✓] PARI installed successfully!" -ForegroundColor Green
Write-Host "Run 'pari-cli' to get started!" -ForegroundColor Cyan
