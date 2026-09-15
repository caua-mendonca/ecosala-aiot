// EcoSala — Firmware ESP32 (Wokwi)
// Le temperatura/umidade (DHT22) e luminosidade aproximada (LDR) e publica
// via MQTT no formato definido em docs/contrato-mqtt.md.

#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <ArduinoJson.h>

// ---------------------------------------------------------------------
// Configuracao (constantes agrupadas)
// ---------------------------------------------------------------------

// Wi-Fi (ambiente de simulacao Wokwi)
constexpr char WIFI_SSID[] = "Wokwi-GUEST";
constexpr char WIFI_PASSWORD[] = "";

// Broker MQTT
// - Rodando via Wokwi VS Code extension + Private IoT Gateway: "host.wokwi.internal"
// - Ver firmware/README.md para o passo a passo completo (inclusive alternativa
//   com broker publico apenas para testes de conectividade).
constexpr char MQTT_HOST[] = "host.wokwi.internal";
constexpr int MQTT_PORT = 1883;
constexpr char MQTT_USERNAME[] = "device";
constexpr char MQTT_PASSWORD[] = "dev-esp32-2026";

// Identificacao do dispositivo / sala (contrato MQTT)
constexpr char ROOM_ID[] = "sala-101";
constexpr char DEVICE_ID[] = "esp32-sala-101";

// Topicos (ver docs/contrato-mqtt.md)
const String TOPIC_TELEMETRY = String("ecosala/v1/") + ROOM_ID + "/" + DEVICE_ID + "/telemetry";
const String TOPIC_STATUS = String("ecosala/v1/") + ROOM_ID + "/" + DEVICE_ID + "/status";

// Pinos dos sensores
constexpr int DHT_PIN = 15;
constexpr int LDR_PIN = 34; // pino somente-ADC (ADC1_CH6)
#define DHT_TYPE DHT22

// Intervalo de publicacao (configuravel)
constexpr unsigned long PUBLISH_INTERVAL_MS = 5000;

// Constantes de conversao aproximada do LDR para lux
// (formula de aproximacao usual para fotoresistores em divisor de tensao;
// os valores nao representam uma calibracao fisica exata — adequados para
// fins de simulacao/demonstracao, conforme indicado em docs/problema.md)
constexpr float LDR_GAMMA = 0.7f;
constexpr float LDR_RL10_KOHM = 50.0f;
constexpr float ADC_MAX_VALUE = 4095.0f;
constexpr float ADC_REF_VOLTAGE = 3.3f;
constexpr float LDR_DIVIDER_RESISTOR_OHM = 2000.0f;

// Reconexao
constexpr unsigned long WIFI_RETRY_DELAY_MS = 500;
constexpr unsigned long MQTT_RETRY_DELAY_MS = 2000;

// ---------------------------------------------------------------------
// Estado global
// ---------------------------------------------------------------------

DHT dht(DHT_PIN, DHT_TYPE);
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

unsigned long lastPublishAt = 0;

struct SensorReading {
  float temperature;
  float humidity;
  float luminosity;
};

// ---------------------------------------------------------------------
// Wi-Fi
// ---------------------------------------------------------------------

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  Serial.printf("Conectando ao Wi-Fi \"%s\"...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(WIFI_RETRY_DELAY_MS);
    Serial.print(".");
  }

  Serial.printf("\nWi-Fi conectado. IP: %s\n", WiFi.localIP().toString().c_str());
}

// ---------------------------------------------------------------------
// MQTT
// ---------------------------------------------------------------------

void connectMqtt() {
  while (!mqttClient.connected()) {
    Serial.printf("Conectando ao broker MQTT %s:%d...\n", MQTT_HOST, MQTT_PORT);

    // LWT: se a conexao cair sem publicar "offline" explicitamente, o
    // broker publica esta mensagem automaticamente (retained).
    bool connected = mqttClient.connect(
        DEVICE_ID,
        MQTT_USERNAME,
        MQTT_PASSWORD,
        TOPIC_STATUS.c_str(),
        1,     // willQos
        true,  // willRetain
        "offline"
    );

    if (connected) {
      Serial.println("MQTT conectado.");
      mqttClient.publish(TOPIC_STATUS.c_str(), "online", true);
    } else {
      Serial.printf("Falha ao conectar (rc=%d). Tentando novamente em %lums.\n",
                    mqttClient.state(), MQTT_RETRY_DELAY_MS);
      delay(MQTT_RETRY_DELAY_MS);
    }
  }
}

// ---------------------------------------------------------------------
// Sensores
// ---------------------------------------------------------------------

float readLuminosityLux() {
  int analogValue = analogRead(LDR_PIN);
  float voltage = (analogValue / ADC_MAX_VALUE) * ADC_REF_VOLTAGE;

  if (voltage <= 0.0f) {
    return 0.0f;
  }

  float resistanceKOhm = (LDR_DIVIDER_RESISTOR_OHM * voltage / (ADC_REF_VOLTAGE - voltage)) / 1000.0f;
  float lux = pow(LDR_RL10_KOHM * pow(10, LDR_GAMMA) / resistanceKOhm, 1.0f / LDR_GAMMA);
  return lux;
}

// Retorna false quando a leitura do DHT22 e invalida (NaN) — nesse caso a
// leitura nao deve ser publicada.
bool readSensors(SensorReading &reading) {
  reading.temperature = dht.readTemperature();
  reading.humidity = dht.readHumidity();
  reading.luminosity = readLuminosityLux();

  if (isnan(reading.temperature) || isnan(reading.humidity)) {
    Serial.println("Leitura invalida do DHT22 (NaN) — descartando.");
    return false;
  }

  return true;
}

// ---------------------------------------------------------------------
// Payload / publicacao
// ---------------------------------------------------------------------

size_t buildPayload(const SensorReading &reading, char *buffer, size_t bufferSize) {
  StaticJsonDocument<256> doc;

  doc["device_id"] = DEVICE_ID;
  doc["room_id"] = ROOM_ID;
  doc["timestamp"] = (unsigned long)(millis() / 1000);
  doc["temperature"] = reading.temperature;
  doc["humidity"] = reading.humidity;
  doc["luminosity"] = reading.luminosity;

  return serializeJson(doc, buffer, bufferSize);
}

void publishTelemetry(const SensorReading &reading) {
  char payload[256];
  size_t length = buildPayload(reading, payload, sizeof(payload));

  bool published = mqttClient.publish(TOPIC_TELEMETRY.c_str(), (const uint8_t *)payload, length, false);

  Serial.printf("[%s] publish %s -> %s\n",
                published ? "OK" : "FALHA",
                TOPIC_TELEMETRY.c_str(),
                payload);
}

// ---------------------------------------------------------------------
// Ciclo principal
// ---------------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  dht.begin();
  analogReadResolution(12); // 0-4095

  connectWiFi();
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  connectMqtt();
}

void loop() {
  connectWiFi();

  if (!mqttClient.connected()) {
    connectMqtt();
  }
  mqttClient.loop();

  unsigned long now = millis();
  if (now - lastPublishAt >= PUBLISH_INTERVAL_MS) {
    lastPublishAt = now;

    SensorReading reading;
    if (readSensors(reading)) {
      publishTelemetry(reading);
    }
  }
}
