# Sobe o EcoSala no Windows: gera os segredos (se ainda nao existirem) e roda o Docker Compose.
# Uso (na raiz do projeto):  powershell -ExecutionPolicy Bypass -File scripts\iniciar.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path ".env")) { python scripts/gerar_segredos.py }
docker compose up -d --build
Write-Host "`nAguardando os servicos ficarem saudaveis..."
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 10
    $ps = docker compose ps --format "{{.Service}} {{.Status}}"
    $starting = $ps | Select-String -Pattern "starting|unhealthy|Restarting"
    if (-not $starting) { break }
}
docker compose ps
Write-Host "`nAbra http://localhost:8080  (usuarios e senhas em credenciais-demo.txt)"
