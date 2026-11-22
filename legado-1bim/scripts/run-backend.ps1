# Sobe o backend (FastAPI/Uvicorn) em modo desenvolvimento.
# Pre-requisitos: Mosquitto e InfluxDB rodando localmente (ver infra/),
# e backend\.env preenchido (copie de backend\.env.example).
# Uso (a partir da raiz do repositorio):
#   .\scripts\run-backend.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$venvPython = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Error "Ambiente virtual nao encontrado em backend\.venv. Rode primeiro:`n  cd backend`n  python -m venv .venv`n  .\.venv\Scripts\python.exe -m pip install -e `".[dev]`""
    exit 1
}

if (-not (Test-Path (Join-Path $backend ".env"))) {
    Write-Warning "backend\.env nao encontrado. Copiando de .env.example (ajuste os valores depois)."
    Copy-Item (Join-Path $backend ".env.example") (Join-Path $backend ".env")
}

Push-Location $backend
try {
    & $venvPython -m uvicorn app.main:app --reload
}
finally {
    Pop-Location
}
