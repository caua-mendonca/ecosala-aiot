# EcoSala — Monitoramento de Conforto Ambiental em Salas de Aula

> Projeto acadêmico (Smart Campus) que monitora temperatura, umidade e
> luminosidade de salas de aula via ESP32 + MQTT + InfluxDB, com dashboard em
> Vue.js.

Este README está em construção e será completado na Etapa 9 (Documentação e
entrega), com pré-requisitos, passo a passo de instalação, variáveis de
ambiente, prints e roteiro de demonstração.

## Integrantes do grupo

> Substitua pelos nomes reais do grupo.

- Integrante 1
- Integrante 2
- Integrante 3

## Documentação de planejamento (Etapa 1 — concluída)

- [`docs/problema.md`](docs/problema.md) — problema, público-alvo e solução.
- [`docs/arquitetura.md`](docs/arquitetura.md) — diagrama de arquitetura
  (Mermaid), decisões técnicas e plano de evolução para o 2º bimestre.
- [`docs/contrato-mqtt.md`](docs/contrato-mqtt.md) — tópicos MQTT, formato de
  payload e requisitos de conexão.

## Roteiro de implementação

| Etapa | Descrição | Status |
|---|---|---|
| 1 | Planejamento (docs) | ✅ |
| 2 | Infraestrutura (Mosquitto + InfluxDB) | ⏳ |
| 3 | Firmware (Wokwi) + simulador Python | ⏳ |
| 4 | Backend — domínio e casos de uso | ⏳ |
| 5 | Backend — infraestrutura (MQTT + InfluxDB) | ⏳ |
| 6 | Backend — API REST | ⏳ |
| 7 | Frontend (Vue 3 + TS) | ⏳ |
| 8 | Qualidade (lint, tipagem, testes) | ⏳ |
| 9 | Documentação e entrega | ⏳ |
| 10 | Roteiro de demonstração | ⏳ |

## Estrutura do repositório (planejada)

```
ecosala/
├── docs/            # documentação
├── firmware/        # ESP32 / Wokwi
├── infra/           # Mosquitto e InfluxDB
├── backend/         # FastAPI + Clean Architecture
└── frontend/        # Vue 3 + TypeScript + Vite
```
