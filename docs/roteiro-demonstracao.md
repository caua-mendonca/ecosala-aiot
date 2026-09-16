# Roteiro de Demonstração — EcoSala

Este roteiro mapeia cada critério de avaliação para o que deve ser mostrado
ao vivo, na ordem sugerida de apresentação.

## Checklist pré-apresentação (fazer antes de começar)

- [ ] **Mosquitto** rodando (`mosquitto -c infra/mosquitto/mosquitto.conf -v`), sem erros no terminal.
- [ ] **InfluxDB** rodando (`influxd`), acessível em `http://localhost:8086`.
- [ ] Arquivo `infra/mosquitto/passwd` gerado com os usuários `device` e `backend`.
- [ ] Token do InfluxDB válido e presente em `backend/.env`.
- [ ] **Backend** rodando (`uvicorn app.main:app --reload`) — conferir `/api/v1/health` retornando `mqtt_connected: true` e `influxdb_connected: true`.
- [ ] **Frontend** rodando (`npm run dev`) e apontando para a API correta (`frontend/.env`).
- [ ] Simulação do **Wokwi** aberta e testada (ou, como alternativa, o simulador Python `backend/scripts/simulate_device.py` funcionando).
- [ ] Deixar o simulador (Wokwi ou Python) publicando por alguns minutos **antes** da apresentação, para já existir histórico acumulado no InfluxDB (necessário para o gráfico da tela de Histórico).
- [ ] Terminal aberto com `mosquitto_sub -h localhost -p 1883 -u backend -P <senha> -t 'ecosala/#' -v`, pronto para mostrar mensagens em tempo real.
- [ ] **Plano B** confirmado: se o Wokwi falhar durante a apresentação, o simulador Python (`backend/scripts/simulate_device.py`) publica no mesmo formato e resolve a demonstração sem interrupção.

## Roteiro (mapeado para a nota)

### 1. Problema e proposta (1,0 ponto)

- Abrir a aba **Sobre** do dashboard (problema, solução, fluxo de dados).
- Complementar citando [`docs/problema.md`](problema.md) (público-alvo, faixas de conforto).

### 2. Frontend Vue 3 + TS + Vite (2,0 pontos)

- Rodar `npm run dev` ao vivo (mostrar o comando, não só a página já aberta).
- Navegar entre Dashboard → Histórico → Sobre pelo menu.
- Rodar `npm run type-check` no terminal e mostrar que passa sem erros (`vue-tsc`, `strict: true`, sem `any`).

### 3. Dispositivo Wokwi (1,5 ponto)

- Mostrar a simulação rodando (ESP32 + DHT22 + fotoresistor).
- **Alterar a temperatura no DHT22** e a luz no LDR durante a simulação, mostrando os valores mudando no serial monitor do Wokwi.
- Mostrar o firmware publicando (`Serial.printf` de `publishTelemetry`) a cada 5 segundos.

### 4. MQTT + Mosquitto (2,0 pontos)

- Mostrar o terminal com `mosquitto_sub -t 'ecosala/#' -v` recebendo as mensagens de telemetria em tempo real conforme o Wokwi publica.
- **Parar a simulação do Wokwi** (ou fechar a aba) e mostrar o tópico de status mudando para `offline` (LWT) — e o dashboard refletindo "Offline" no card da sala correspondente.

### 5. Backend Python (1,0 ponto)

- Mostrar os logs do backend recebendo, validando e classificando as leituras (nível `INFO`, sem `print()`).
- Abrir `http://localhost:8000/docs` (Swagger) e executar `/api/v1/health` (mostrando `mqtt_connected`/`influxdb_connected`) e `/api/v1/readings/latest` ao vivo.

### 6. Persistência InfluxDB (1,5 ponto)

- Abrir o **Data Explorer** do InfluxDB (`http://localhost:8086`), selecionar o bucket `ecosala`, measurement `environment`, e mostrar os pontos gravados (tags `device_id`/`room_id`/`comfort_status`, fields `temperature`/`humidity`/`luminosity`).

### 7. Dashboard (1,0 ponto)

- No Dashboard, alterar a temperatura no Wokwi até sair da faixa ideal (ex.: acima de 26°C) e mostrar o card mudando de **OK** para **Atenção** e depois **Crítico** em tempo real (atualização automática a cada 5s).
- Ir para a tela **Histórico**, selecionar o dispositivo e um período (ex.: 15 minutos), mostrar o gráfico de linhas com as linhas de referência das faixas ideais e a tabela de mínimo/máximo/média.

## Se algo falhar durante a apresentação

- **Wokwi instável/sem internet**: rode o simulador Python (`backend/scripts/simulate_device.py`) — ele publica no mesmo formato e o restante do pipeline (Mosquitto → Backend → InfluxDB → Dashboard) continua funcionando normalmente.
- **Backend não conecta ao Mosquitto/InfluxDB**: confirme que ambos estão rodando (`Test-NetConnection -ComputerName localhost -Port 1883` / `8086`) e que `backend/.env` tem as credenciais corretas.
- **Dashboard sem dados**: verifique `/api/v1/readings/latest` diretamente no Swagger antes de suspeitar do frontend — se a API já retorna vazio, o problema está no backend/MQTT, não na tela.
