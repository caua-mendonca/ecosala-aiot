# Contrato MQTT — EcoSala

Este documento define os tópicos, formatos de payload, QoS e convenções de
conexão usados na comunicação entre o firmware (ESP32) e o backend, via
Mosquitto.

## 1. Convenção de tópicos

Prefixo de versão do contrato: `ecosala/v1`.

| Finalidade | Tópico | Direção | QoS | Retained |
|---|---|---|---|---|
| Telemetria | `ecosala/v1/{room_id}/{device_id}/telemetry` | dispositivo → backend | 1 | não |
| Status (LWT) | `ecosala/v1/{room_id}/{device_id}/status` | dispositivo → backend | 1 | **sim** |
| Comando (reservado, 2º bimestre) | `ecosala/v1/{room_id}/{device_id}/command` | backend → dispositivo | 1 | não |

- `{room_id}`: identificador da sala, ex.: `sala-101`.
- `{device_id}`: identificador único do dispositivo, ex.: `esp32-sala-101`.

O backend assina com wildcards:
- `ecosala/v1/+/+/telemetry`
- `ecosala/v1/+/+/status`

## 2. Payload de telemetria

Tópico: `ecosala/v1/{room_id}/{device_id}/telemetry`

```json
{
  "device_id": "esp32-sala-101",
  "room_id": "sala-101",
  "timestamp": 1760000000,
  "temperature": 27.4,
  "humidity": 58.1,
  "luminosity": 412
}
```

| Campo | Tipo | Descrição | Faixa física plausível |
|---|---|---|---|
| `device_id` | string | Identificador único do dispositivo | não vazio |
| `room_id` | string | Identificador da sala | não vazio |
| `timestamp` | integer | Unix timestamp (segundos, UTC) da leitura no dispositivo | > 0 |
| `temperature` | float | Temperatura em °C | -40.0 a 80.0 |
| `humidity` | float | Umidade relativa em % | 0.0 a 100.0 |
| `luminosity` | float | Luminosidade aproximada em lux | 0 a 100000 |

Mensagens fora dessas faixas físicas plausíveis, com campos ausentes ou com
tipos incorretos são consideradas **inválidas**: o backend registra um log de
aviso e descarta a mensagem, sem interromper o serviço (ver
`backend/app/infrastructure/mqtt/payload_schema.py`, Etapa 5).

## 3. Payload de status (Last Will and Testament)

Tópico: `ecosala/v1/{room_id}/{device_id}/status`

Payload (texto simples, retained):

- `"online"` — publicado pelo dispositivo logo após conectar ao broker.
- `"offline"` — configurado como **Last Will** na conexão MQTT do
  dispositivo: o broker publica automaticamente esta mensagem se o
  dispositivo cair sem se desconectar corretamente (perda de conexão,
  simulação parada, etc.).

O flag `retained=true` garante que qualquer novo assinante (ex.: o backend
reiniciando) receba imediatamente o último status conhecido de cada
dispositivo, sem esperar a próxima leitura.

## 4. Payload de comando (reservado — 2º bimestre)

Tópico: `ecosala/v1/{room_id}/{device_id}/command`

Formato previsto (a ser detalhado quando os atuadores forem definidos):

```json
{
  "command": "SET_FAN_SPEED",
  "value": 2,
  "issued_at": 1760000000
}
```

Não implementado no 1º bimestre — apenas reservado no espaço de nomes de
tópicos para não exigir migração posterior.

## 5. Requisitos de conexão

- **QoS 1** obrigatório na telemetria (garantia de entrega ao menos uma vez).
- **`client_id` único** por dispositivo e por processo backend, para evitar
  desconexões por conflito de identificador no broker.
- **Reconexão automática**: tanto o firmware (`PubSubClient::connect` em loop
  com backoff) quanto o backend (`paho-mqtt`, `reconnect_delay_set`) devem se
  reconectar automaticamente após queda de conexão.
- **Autenticação obrigatória**: `allow_anonymous false` no Mosquitto, com
  usuários separados para dispositivos (`device`) e para o backend
  (`backend`), definidos em `infra/mosquitto/passwd` (ver Etapa 2).
- **Intervalo de publicação**: configurável no firmware, padrão de
  **5 segundos**.

## 6. Exemplo de teste manual (linha de comando)

Assinar todos os tópicos do EcoSala:

```bash
mosquitto_sub -h localhost -p 1883 -u backend -P <senha> -t 'ecosala/#' -v
```

Publicar uma leitura de teste manualmente:

```bash
mosquitto_pub -h localhost -p 1883 -u device -P <senha> \
  -t 'ecosala/v1/sala-101/esp32-sala-101/telemetry' \
  -m '{"device_id":"esp32-sala-101","room_id":"sala-101","timestamp":1760000000,"temperature":27.4,"humidity":58.1,"luminosity":412}' \
  -q 1
```
