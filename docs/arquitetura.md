# Arquitetura — EcoSala AIoT

## Visão por camadas

| Camada | Tecnologia | Papel |
|---|---|---|
| Dispositivo | Simulador Python (`backend/simulator`) | 3 salas + estação externa; sensores, atuadores e ar-condicionados que degradam |
| Borda | MQTT + Mosquitto | protocolo leve entre dispositivo e aplicação, nos dois sentidos, com ACL |
| Gateway | Python (paho-mqtt + pika) | traduz MQTT ⇄ AMQP e quebra cada leitura em uma mensagem por dispositivo |
| Barramento | RabbitMQ | exchanges topic/direct, 8 filas com consumidores diferentes, DLQ |
| Telemetria | InfluxDB | séries temporais (bucket `telemetria`) e amostra sintética (bucket `lab`) |
| Relacional | PostgreSQL | usuários, dispositivos, configurações, regras, alertas, jobs, modelos, auditoria |
| IA | numpy, pandas, scikit-learn | gerador sintético, 2 regressões, inferência em tempo real |
| LLM | Ollama (`llama3.2:3b`) | assistente local, sem nuvem |
| Backend | FastAPI | REST, WebSocket, regras de negócio, consumidores, integração |
| Frontend | Vue 3 + TS + Vite, Chart.js, Three.js | dashboard, 3D, IA, mensageria, assistente |
| Infra | Docker Compose | um comando, healthchecks e ordem de subida |

## Decisões

- **Uma imagem Python para todos os serviços**: o mesmo código de features/física é usado por gerador,
  treino, simulador e inferência — impossível divergir entre treino e produção.
- **Simulador e gerador compartilham `physics.py`**: o modelo treinado com dados sintéticos reconhece o
  comportamento do equipamento ao vivo.
- **Tempo simulado de 10 min por leitura** igual ao intervalo dos dados sintéticos: as janelas de 1 h e
  24 h significam a mesma coisa no treino e na inferência.
- **RUL limitada a 7 dias (168 h)**: antes do início da degradação não há sinal para prever o tempo exato;
  acima disso o equipamento é considerado "sem sinal de falha".
- **Regressão estratificada por equipamento**: garante máquinas que falham em treino, validação e teste.
- **Modelo só entra em uso se vencer a base simples** em MAE e R² nos dois alvos.
- **Jobs pesados em fila** (`q.jobs.*`): a API responde 202 imediatamente; o worker roda em thread separada
  para não perder o heartbeat do RabbitMQ, publica progresso e o PostgreSQL guarda o histórico.
- **Hot reload do modelo**: o worker publica `model.updated`; a inferência recarrega sem reiniciar.
- **WebSocket com ticket**: o JWT nunca aparece na URL (logs de proxy), o ticket vale 30 s e uma vez.
- **Cena 3D lê um store**: o loop de animação lê o estado mais recente; mensagens não redesenham a cena.

## Evolução em relação ao 1º bimestre

O desenho do 1º bimestre já previa (docs do legado, seção 4): novos sensores, tópico `command` reservado,
banco relacional e Docker. Tudo isso foi implementado, e acrescentamos RabbitMQ, IA, 3D e LLM.
