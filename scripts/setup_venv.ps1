# Create or refresh the canonical Premalytics venv (Python 3.12).
# Usage: .\scripts\setup_venv.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$VenvPython = Join-Path $Root "data-pipeline\venv\Scripts\python.exe"
$VenvPip = Join-Path $Root "data-pipeline\venv\Scripts\pip.exe"

Write-Host "Creating venv with py -3.12 at data-pipeline\venv ..."
py -3.12 -m venv "data-pipeline\venv"

Write-Host "Installing dependencies ..."
& $VenvPython -m pip install -U pip
& $VenvPip install -r "requirements.txt" -r "ml\requirements.txt"

Write-Host ""
Write-Host "Done. Python version:"
& $VenvPython --version
Write-Host "Activate: .\data-pipeline\venv\Scripts\Activate.ps1"
