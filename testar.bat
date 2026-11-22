@echo off
REM EcoSala: espera o Docker, gera segredos, sobe tudo e grava o progresso em logs\subida.txt
cd /d "%~dp0"
if not exist logs mkdir logs
echo Iniciando... > logs\subida.txt
echo Aguardando o Docker Desktop ficar pronto...
set /a n=0
:espera
docker info >nul 2>&1
if %errorlevel%==0 goto pronto
set /a n+=1
echo   Docker ainda nao respondeu (%n%)... >> logs\subida.txt
if %n% GEQ 60 goto semdocker
timeout /t 5 /nobreak >nul
goto espera
:semdocker
echo ERRO: Docker nao respondeu em 5 minutos. Abra o Docker Desktop. >> logs\subida.txt
echo ERRO: Docker nao respondeu. Abra o Docker Desktop e rode de novo.
pause
exit /b 1
:pronto
echo Docker pronto. >> logs\subida.txt
if not exist .env (
  python scripts\gerar_segredos.py >> logs\subida.txt 2>&1
  if not exist .env py scripts\gerar_segredos.py >> logs\subida.txt 2>&1
)
echo === BUILD E SUBIDA (pode demorar 10-20 min na 1a vez) === >> logs\subida.txt
echo Subindo os containers... acompanhe em logs\subida.txt
docker compose up -d --build >> logs\subida.txt 2>&1
echo === FIM DO UP: codigo %errorlevel% === >> logs\subida.txt
timeout /t 90 /nobreak >nul
docker compose ps -a >> logs\subida.txt 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\diagnostico.ps1
echo === PRONTO === >> logs\subida.txt
echo.
echo Pronto. Abra http://localhost:8080
pause
