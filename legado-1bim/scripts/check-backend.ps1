# Roda testes, lint (ruff) e checagem de tipos (mypy --strict) do backend.
# Uso (a partir da raiz do repositorio):
#   .\scripts\check-backend.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$venvPython = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Error "Ambiente virtual nao encontrado em backend\.venv. Rode primeiro:`n  cd backend`n  python -m venv .venv`n  .\.venv\Scripts\python.exe -m pip install -e `".[dev]`""
    exit 1
}

Push-Location $backend
try {
    Write-Host "==> pytest" -ForegroundColor Cyan
    & $venvPython -m pytest
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "`n==> ruff check" -ForegroundColor Cyan
    & $venvPython -m ruff check app tests
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "`n==> mypy --strict" -ForegroundColor Cyan
    & $venvPython -m mypy app
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}

Write-Host "`nBackend OK." -ForegroundColor Green
