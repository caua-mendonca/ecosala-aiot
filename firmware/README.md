# Firmware EcoSala — ESP32 (Wokwi)

Projeto PlatformIO simulado no Wokwi: le temperatura/umidade (DHT22) e
luminosidade aproximada (LDR) e publica via MQTT, conforme
[`docs/contrato-mqtt.md`](../docs/contrato-mqtt.md).

## Arquivos

- `platformio.ini` — dependências (`PubSubClient`, `DHT sensor library`,
  `ArduinoJson`) e placa (`esp32dev`).
- `diagram.json` — circuito simulado no Wokwi (ESP32 DevKit-C V4 + DHT22 +
  fotoresistor).
- `wokwi.toml` — aponta o simulador para o binário compilado pelo PlatformIO.
- `src/main.cpp` — firmware.

## ⚠️ Importante: conectividade do Wokwi com o Mosquitto local

O simulador Wokwi roda **no navegador** (ou na extensão do VS Code), e por
padrão **não enxerga o `localhost` da sua máquina** — então um broker
Mosquitto rodando localmente não é alcançável diretamente pelo simulador.

### Opção recomendada — Wokwi para VS Code + Private IoT Gateway

1. Instale a extensão **Wokwi for VS Code** (Wokwi Simulator) no VS Code.
2. Ative a licença gratuita da extensão (necessária para simulação com
   Wi-Fi/rede).
3. Abra a pasta `firmware/` no VS Code.
4. Compile o projeto com o PlatformIO (`pio run`) ou deixe a extensão
   compilar automaticamente ao iniciar a simulação.
5. Inicie a simulação pela paleta de comandos: **"Wokwi: Start Simulator"**.
6. A extensão expõe automaticamente um **Private IoT Gateway**, que permite
   que o firmware simulado acesse serviços da sua máquina através do
   hostname especial `host.wokwi.internal` — é exatamente o valor já
   configurado em `MQTT_HOST` no `src/main.cpp`.
7. Com o Mosquitto rodando localmente na porta `1883` (ver
   `infra/mosquitto/mosquitto.conf`), o firmware simulado deverá conectar
   normalmente.

Mais detalhes oficiais: documentação da Wokwi sobre "Private Gateway" /
`host.wokwi.internal` (extensão Wokwi para VS Code).

### Alternativa apenas para testes de conectividade (não usar na demonstração)

Se quiser validar rapidamente que o firmware compila e publica mensagens
MQTT **sem** depender do Mosquitto local (por exemplo, testando no
simulador Wokwi via navegador, que não acessa `host.wokwi.internal`), é
possível apontar temporariamente `MQTT_HOST` para um broker público de
testes (ex.: `test.mosquitto.org`, porta `1883`, sem autenticação) e usar
`mosquitto_sub` para ver as mensagens chegando em um tópico exclusivo seu.

Isso serve **apenas** para confirmar que o firmware publica corretamente o
JSON esperado — a demonstração oficial do projeto deve sempre usar o
Mosquitto local via Private IoT Gateway, pois é isso que alimenta o backend
e o dashboard.

## Plano B para a apresentação

Caso o Wokwi (navegador ou extensão) apresente instabilidade no dia da
demonstração, use o simulador Python
[`backend/scripts/simulate_device.py`](../backend/scripts/simulate_device.py),
que publica dados no mesmíssimo formato do firmware, diretamente para o
Mosquitto local — sem depender do Wokwi.

## Como testar

Com o Mosquitto local rodando (ver `infra/mosquitto/`), em outro terminal:

```powershell
mosquitto_sub -h localhost -p 1883 -u backend -P <senha_backend> -t 'ecosala/#' -v
```

Inicie a simulação no Wokwi (VS Code) e observe as mensagens de telemetria
e de status (`online`) aparecendo no terminal a cada 5 segundos. Pare a
simulação (feche o Wokwi) e verifique que, após o timeout de keepalive, o
broker publica automaticamente `offline` no tópico de status (LWT).
