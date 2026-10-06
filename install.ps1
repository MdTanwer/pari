# PARI Installer for Windows (PowerShell)
# Usage: irm https://raw.githubusercontent.com/MdTanwer/pari/main/install.ps1 | iex

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

# 1. Prefer uv if available
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "[+] Found uv. Installing pari via uv tool..." -ForegroundColor Green
    try { uv tool install --force pari } catch { uv tool install --force "git+$RepoUrl" }
    Write-Host "`n[✓] PARI installed successfully! Type 'pari' to start." -ForegroundColor Cyan
    exit
}

# 2. Prefer pipx if available
if (Get-Command pipx -ErrorAction SilentlyContinue) {
    Write-Host "[+] Found pipx. Installing pari via pipx..." -ForegroundColor Green
    try { pipx install --force pari } catch { pipx install --force "git+$RepoUrl" }
    Write-Host "`n[✓] PARI installed successfully! Type 'pari' to start." -ForegroundColor Cyan
    exit
}

# 3. Fallback: Use standard python to create isolated venv
$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    $PythonCmd = Get-Command py -ErrorAction SilentlyContinue
}

if ($PythonCmd) {
    Write-Host "[*] Setting up isolated environment in $VenvDir..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

    & $PythonCmd.Source -m venv $VenvDir
    $VenvPip = Join-Path $ScriptsDir "pip.exe"

    & $VenvPip install --upgrade pip --quiet
    try { & $VenvPip install pari --quiet } catch { & $VenvPip install "git+$RepoUrl" --quiet }

    # Ensure Scripts directory is in user PATH
    $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($UserPath -notlike "*$ScriptsDir*") {
        Write-Host "[+] Adding $ScriptsDir to User PATH..." -ForegroundColor Yellow
        [Environment]::SetEnvironmentVariable("Path", "$UserPath;$ScriptsDir", "User")
        $env:Path = "$env:Path;$ScriptsDir"
    }

    Write-Host "`n[✓] PARI installed successfully!" -ForegroundColor Green
    Write-Host "Run 'pari' to get started (restart PowerShell if the command is not immediately found)." -ForegroundColor Cyan
} else {
    Write-Host "Error: Python 3.11+ is required but not found on your system." -ForegroundColor Red
    Write-Host "Please install Python from https://www.python.org/ or via 'winget install Python.Python.3.11'." -ForegroundColor Red
    exit 1
}
