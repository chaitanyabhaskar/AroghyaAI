# GenAI Generated code - Start
# Local dev launcher for Windows PowerShell.
#   .\run.ps1          -> set up venv, install deps, start on http://localhost:8000
#   .\run.ps1 -NoReload -> start without the auto-reloader

param(
    [int]$Port = 8000,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv .venv
}

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

Write-Host "Installing dependencies..." -ForegroundColor Cyan
& $python -m pip install --upgrade pip --quiet
& $python -m pip install -r requirements.txt --quiet

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env - add your LLM_API_KEY, then restart." -ForegroundColor Yellow
}

New-Item -ItemType Directory -Path "data" -Force | Out-Null

Write-Host "ArogyaAI running at http://localhost:$Port" -ForegroundColor Green

$args = @("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "$Port")
if (-not $NoReload) { $args += "--reload" }

& $python @args
# GenAI Generated code - End
