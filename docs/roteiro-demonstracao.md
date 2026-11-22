# Roteiro da demonstração (16/11) — na ordem pedida

Antes da aula (com internet, na véspera): `python scripts/gerar_segredos.py`, `docker compose up -d --build`
e espere tudo ficar saudável (o LLM é baixado só na primeira vez). Deixe aberto o `credenciais-demo.txt`.
Na aula, se quiser mostrar a subida "do zero": `docker compose down` e `docker compose up -d`.

| # | Passo | Como mostrar | Quem fala |
|---|---|---|---|
| 1 | `docker compose up` com containers saudáveis | `docker compose up -d` e `docker compose ps` (todos `healthy`; `rabbit-init` e `ollama-init` `Exited (0)`) | |
| 2 | Login e os três papéis | Entrar como `visualizador` (botões de comando não aparecem), `operador` (comanda) e `administrador` (Laboratório, Treino, Auditoria) | |
| 3 | Simulador enviando dados pelo Mosquitto | `docker compose logs -f simulator` e `docker compose exec mosquitto sh -c 'mosquitto_sub -u gateway -P "$MQTT_GATEWAY_PASSWORD" -t "ecosala/#" -v -C 5'` | |
| 4 | FastAPI e documentação | http://localhost:8080/docs — fazer `POST /api/v1/auth/login`, **Authorize** e testar `GET /api/v1/devices` | |
| 5 | Mensageria + consumidor parado | Página **Mensageria**: filas, taxas, consumidores, últimas mensagens. Rodar `docker compose stop influx-writer` → `q.influx` cresce (consumidores = 0) → `docker compose start influx-writer` → esvazia. Botão **Enviar mensagem inválida** → aparece na DLQ com a mensagem preservada | |
| 6 | InfluxDB e PostgreSQL | **Histórico** (consulta ao InfluxDB) e http://127.0.0.1:8086 (Data Explorer, bucket `telemetria`, measurement `sensor`). pgAdmin http://127.0.0.1:5050: tabelas `devices`, `rules`, `alerts`, `audit_log`. Página **Dispositivos** (cadastro) e **Auditoria** | |
| 7 | Dashboard em tempo real (WebSocket) | **Dashboard**: valores mudando a cada 2 s, gráficos e indicadores | |
| 8 | Regra automática + controle Web | Regra (opção A): desligar `ac-101` pelo Dashboard → a temperatura sobe e, acima de 28 °C, `vent-101` liga sozinho. Opção B (mais rápida): na página **Dispositivos** baixar o limite "Temperatura alta liga ventilação (sala-101)" para 20 → `vent-101` liga sozinho (aparece na Auditoria como `motor-de-regras`). Web: no **Dashboard** clicar **Ligar/Desligar** em `luz-101` → luminosidade sobe/cai ~450 lux nas leituras seguintes e chega o retorno do dispositivo | |
| 9 | Laboratório de Dados | Como `administrador`: padrão (100 equipamentos, 90 dias ≈ 10,4 milhões de leituras) → **Gerar dados**; a API responde na hora e a barra de progresso avança (fila `q.jobs.generate`) | |
| 10 | Treinamento e métricas | **Treinamento** → escolher o dataset → **Treinar modelos**. Ler MAE/RMSE/R² × base simples, previsto × real, importância dos atributos; a nova versão entra em uso sem reiniciar a inferência | |
| 11 | Falha injetada | **Insights** (ou clique no ar-condicionado na cena 3D) → `ac-102` → modo *superaquecimento* → **Injetar falha**. Em ~3–5 min: saúde cai, vida útil diminui ("deve falhar em cerca de X h"), alerta abre, condensadora fica vermelha e treme mais no **Gêmeo 3D**, e a sinalização `alarme-102` liga sozinha (regra de alerta) | |
| 12 | Assistente LLM local | **Assistente**: "Qual equipamento está com a pior saúde e o que devo fazer?", "O que significa o alerta aberto?", "Explique as métricas do último treino". Mostrar "Ver resumo enviado ao LLM" | |

Extras para perguntas:

- Pausar o simulador (Dashboard → **Pausar simulador**): a cena 3D congela e avisa "Sem dados em tempo real".
- Por que dois brokers? MQTT é leve para a borda (dispositivos); RabbitMQ distribui internamente com filas
  duráveis, roteamento por tópico, ack, DLQ e consumidores independentes.
- Por que divisão por equipamento? Linhas vizinhas da mesma máquina são quase iguais; misturar inflaria as métricas.
- Por que histerese? Evita alertas e atuadores "piscando" perto do limite.
