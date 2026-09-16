#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <ArduinoJson.h>
#include <time.h>

constexpr char WIFI_SSID[] = "Wokwi-GUEST";
constexpr char WIFI_PASSWORD[] = "";

constexpr char MQTT_HOST[] = "host.wokwi.internal";
constexpr int MQTT_PORT = 1883;
constexpr char MQTT_USERNAME[] = "device";
constexpr char MQTT_PASSWORD[] = "dev-esp32-2026";

constexpr char ROOM_ID[] = "sala-101";
constexpr char DEVICE_ID[] = "esp32-sala-101";

const String TOPIC_TELEMETRY = String("ecosala/v1/") + ROOM_ID + "/" + DEVICE_ID + "/telemetry";
const String TOPIC_STATUS = String("ecosala/v1/") + ROOM_ID + "/" + DEVICE_ID + "/status";

constexpr int DHT_PIN = 15;
constexpr int LDR_PIN = 34;
#define DHT_TYPE DHT22

constexpr unsigned long PUBLISH_INTERVAL_MS = 5000;

constexpr float LDR_GAMMA = 0.7f;
constexpr float LDR_RL10_KOHM = 50.0f;
constexpr float ADC_MAX_VALUE = 4095.0f;
constexpr float ADC_REF_VOLTAGE = 3.3f;
constexpr float LDR_DIVIDER_RESISTOR_OHM = 2000.0f;

constexpr unsigned long WIFI_RETRY_DELAY_MS = 500;
constexpr unsigned long MQTT_RETRY_DELAY_MS = 2000;

constexpr char NTP_SERVER[] = "pool.ntp.org";
constexpr long GMT_OFFSET_SEC = 0;
constexpr int DAYLIGHT_OFFSET_SEC = 0;

DHT dht(DHT_PIN, DHT_TYPE);
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

unsigned long lastPublishAt = 0;

struct SensorReading {
  float temperature;
  float humidity;
  float luminosity;
};

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
  configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER);
}

void connectMqtt() {
  while (!mqttClient.connected()) {
    Serial.printf("Conectando ao broker MQTT %s:%d...\n", MQTT_HOST, MQTT_PORT);

    bool connected = mqttClient.connect(
        DEVICE_ID,
        MQTT_USERNAME,
        MQTT_PASSWORD,
        TOPIC_STATUS.c_str(),
        1,
        true,
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

size_t buildPayload(const SensorReading &reading, char *buffer, size_t bufferSize) {
  StaticJsonDocument<256> doc;

  doc["device_id"] = DEVICE_ID;
  doc["room_id"] = ROOM_ID;
  doc["timestamp"] = (unsigned long)time(nullptr);
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

void setup() {
  Serial.begin(115200);
  dht.begin();
  analogReadResolution(12);

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
