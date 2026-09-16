# Roda type-check (vue-tsc), lint (oxlint + eslint) e testes (vitest) do frontend.
# Uso (a partir da raiz do repositorio):
#   .\scripts\check-frontend.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"

if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Error "Dependencias nao instaladas. Rode primeiro:`n  cd frontend`n  npm install"
    exit 1
}

Push-Location $frontend
try {
    Write-Host "==> vue-tsc --build" -ForegroundColor Cyan
    npm run type-check
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "`n==> lint (oxlint + eslint)" -ForegroundColor Cyan
    npm run lint
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "`n==> vitest" -ForegroundColor Cyan
    npx vitest run
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}

Write-Host "`nFrontend OK." -ForegroundColor Green
