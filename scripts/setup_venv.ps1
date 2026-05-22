# =============================================================================
# setup_venv.ps1 — Create / refresh the canonical Premalytics Python environment
# =============================================================================
#
# WHAT THIS SCRIPT DOES:
#   1. Creates data-pipeline\venv using Python 3.12 (avoid 3.13 wheel issues)
#   2. Upgrades pip
#   3. Installs root requirements.txt + ml\requirements.txt
#
# WHY data-pipeline\venv (not repo-root venv):
#   Documented in docs/VENV.md — single venv for pipeline + ML scripts.
#
# USAGE (from repo root):
#   .\scripts\setup_venv.ps1
#
# THEN:
#   .\data-pipeline\venv\Scripts\Activate.ps1
# =============================================================================

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$VenvPython = Join-Path $Root "data-pipeline\venv\Scripts\python.exe"
$VenvPip = Join-Path $Root "data-pipeline\venv\Scripts\pip.exe"

Write-Host "Creating venv with py -3.12 at data-pipeline\venv ..."
py -3.12 -m venv "data-pipeline\venv"

Write-Host "Installing dependencies ..."
& $VenvPython -m pip install -U pip
# Root: pandas, soccerdata, etc.  ML: scikit-learn, pytest, …
& $VenvPip install -r "requirements.txt" -r "ml\requirements.txt"

Write-Host ""
Write-Host "Done. Python version:"
& $VenvPython --version
Write-Host "Activate: .\data-pipeline\venv\Scripts\Activate.ps1"
