# Coleta o estado e os logs de todos os servicos em logs\diagnostico.txt (para enviar a quem for ajudar).
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force -Path logs | Out-Null
$out = "logs\diagnostico.txt"
"=== $(Get-Date) ===" | Out-File $out -Encoding utf8
"--- docker version" | Out-File $out -Append -Encoding utf8
docker version 2>&1 | Out-File $out -Append -Encoding utf8
"--- docker stats" | Out-File $out -Append -Encoding utf8
docker stats --no-stream 2>&1 | Out-File $out -Append -Encoding utf8
"--- restarts" | Out-File $out -Append -Encoding utf8
docker inspect --format "{{.Name}} restarts={{.RestartCount}} oom={{.State.OOMKilled}}" $(docker compose ps -aq) 2>&1 | Out-File $out -Append -Encoding utf8
"--- docker compose ps" | Out-File $out -Append -Encoding utf8
docker compose ps -a 2>&1 | Out-File $out -Append -Encoding utf8
foreach ($s in (docker compose config --services)) {
    "`n--- logs $s" | Out-File $out -Append -Encoding utf8
    docker compose logs --no-color --tail 80 $s 2>&1 | Out-File $out -Append -Encoding utf8
}
Write-Host "Diagnostico salvo em $out"
