# Sobe o dashboard (Vue/Vite) em modo desenvolvimento.
# Pre-requisito: backend rodando (ver scripts\run-backend.ps1) e
# frontend\.env preenchido (copie de frontend\.env.example).
# Uso (a partir da raiz do repositorio):
#   .\scripts\run-frontend.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"

if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Error "Dependencias nao instaladas. Rode primeiro:`n  cd frontend`n  npm install"
    exit 1
}

if (-not (Test-Path (Join-Path $frontend ".env"))) {
    Write-Warning "frontend\.env nao encontrado. Copiando de .env.example."
    Copy-Item (Join-Path $frontend ".env.example") (Join-Path $frontend ".env")
}

Push-Location $frontend
try {
    npm run dev
}
finally {
    Pop-Location
}
