@echo off
REM Reconstroi o que mudou no codigo, sobe de novo e salva diagnostico em logs\
cd /d "%~dp0"
if not exist logs mkdir logs
echo === ATUALIZANDO === > logs\atualizar.txt
docker compose up -d --build >> logs\atualizar.txt 2>&1
echo === FIM: codigo %errorlevel% === >> logs\atualizar.txt
timeout /t 60 /nobreak >nul
docker compose ps -a >> logs\atualizar.txt 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\diagnostico.ps1
echo === PRONTO === >> logs\atualizar.txt
echo Pronto. Pode fechar esta janela.
pause
