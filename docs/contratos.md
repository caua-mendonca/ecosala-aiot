# Contratos de mensagens

## MQTT (borda) — Mosquitto

| Tópico | Direção | Conteúdo |
|---|---|---|
| `ecosala/v1/<sala>/<nó>/telemetry` | simulador → gateway | leitura do nó: `sensors`, `actuators`, `equipment` |
| `ecosala/v1/<sala>/<nó>/status` | simulador → gateway (retained, LWT) | `online` / `offline` |
| `ecosala/v1/<sala>/<nó>/command` | gateway → simulador | `{id, target, action, params, issued_by, ts}` |
| `ecosala/v1/<sala>/<nó>/ack` | simulador → gateway | `{command_id, target, action, ok, detail}` |

Exemplo de telemetria de um nó:

```json
{"node":"esp32-sala-101","room":"sala-101","ts":"2026-11-16T19:00:00.000+00:00","sim_time":"2026-11-17T10:20+00:00",
 "sensors":{"temp-101":{"type":"temperature","value":25.4},"co2-101":{"type":"co2","value":980}},
 "actuators":{"vent-101":{"type":"fan","state":false},"luz-101":{"type":"light","state":true}},
 "equipment":{"ac-101":{"type":"air_conditioner","enabled":true,"running":true,"failed":false,
   "vibration":1.83,"current":7.9,"temperature":66.2,"ambient_temp":27.1,"load":0.55}}}
```

Ações aceitas: `on`/`off` (atuadores e ar-condicionado), `inject_fault` (`params.mode`, `params.hours`),
`repair` (equipamento) e `pause`/`resume` (tópico `ecosala/v1/sim/simulator/command`).

ACL: usuário `device` só publica telemetry/status/ack e só lê command; usuário `gateway` o contrário.

## AMQP (interno) — RabbitMQ, vhost `ecosala`

Formato único de mensagem:

```json
{"id":"8f1c…","ts":"2026-11-16T19:00:00.000Z","type":"telemetry","device":"temp-101","room":"sala-101",
 "payload":{"kind":"sensor","sensor_type":"temperature","value":25.4,"sim_time":"…"}}
```

`type` ∈ `telemetry`, `status`, `command`, `command.ack`, `prediction`, `alert`, `job.request`,
`job.progress`, `job.done`, `job.failed`, `model.updated`.

| Exchange | Tipo | Routing keys |
|---|---|---|
| `ecosala.telemetry` | topic | `telemetry.<sala>.<tipo>.<id>` (ex.: `telemetry.sala-101.temperature.temp-101`, `telemetry.sala-101.equipment.ac-101`), `status.<sala>.<nó>`, `ack.<sala>.<id>` |
| `ecosala.events` | topic | `prediction.<sala>.equipment.<id>`, `alert.<sala>.<id>`, `job.progress.<job>`, `job.done.<job>`, `model.updated` |
| `ecosala.commands` | topic | `command.<sala>.<id>` |
| `ecosala.jobs` | direct | `job.generate`, `job.train` |
| `ecosala.dlx` | fanout | (mensagens mortas → `q.dlq`) |

Mensagem que falha no processamento recebe `nack(requeue=false)` e vai para `q.dlq` com o conteúdo original
e o cabeçalho `x-death` (fila de origem e motivo).

Usuários e permissões (configure / write / read):

| Usuário | write | read |
|---|---|---|
| `svc-gateway` | `ecosala.telemetry` | `q.commands` |
| `svc-writer` | — | `q.influx` |
| `svc-inference` | `ecosala.events` | `q.inference` |
| `svc-worker` | `ecosala.events` | `q.jobs.generate`, `q.jobs.train` |
| `svc-api` (tag monitoring) | `ecosala.commands`, `ecosala.jobs`, `ecosala.events` | `q.websocket`, `q.rules`, `q.persist`, `q.dlq` |

Nenhum serviço tem permissão de *configure*: a topologia é criada só pelo `rabbit-init` com o administrador.

## Previsão (payload de `prediction`)

```json
{"health":62.4,"rul_h":41.0,"rul_capped":false,"trend":-0.8,"status":"atencao","model_version":2,"failed":false}
```

## Alerta (payload de `alert`)

```json
{"kind":"rul","state":"raised","severity":"critico","message":"Falha prevista em cerca de 41 h","health":62.4,"rul_h":41.0}
```
