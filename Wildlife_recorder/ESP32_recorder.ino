#include <WiFi.h>
#include <WebSocketsClient.h>
#include <driver/i2s.h>

#define I2S_WS  25
#define I2S_SD  33
#define I2S_SCK 32

const char* ssid = "Libra";
const char* password = "12345678";
const char* server_ip = "172.20.10.2";  

WebSocketsClient webSocket;

void setupI2S() {
  const i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = 16000,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_I2S_MSB,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 512,
    .use_apll = false
  };

  const i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_SD
  };

  i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pin_config);
  i2s_zero_dma_buffer(I2S_NUM_0);
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  if (type == WStype_CONNECTED) {
    Serial.println("WebSocket Connected");
    // send ID after connected
    webSocket.sendTXT("ID:ESP32_1");  // change ID for each MIC
  } else if (type == WStype_DISCONNECTED) {
    Serial.println("WebSocket Disconnected");
  }
}

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.println("Connected to WiFi");

  webSocket.begin(server_ip, 8765, "/");
  webSocket.onEvent(webSocketEvent);

  setupI2S();
}

void loop() {
  webSocket.loop();

  static unsigned long startTime = millis();
  static bool recording = true;

  const int sample_count = 256;
  int16_t samples[sample_count];
  size_t bytes_read = 0;

  if (recording) {
    i2s_read(I2S_NUM_0, (void*)samples, sizeof(samples), &bytes_read, portMAX_DELAY);

    if (bytes_read > 0 && webSocket.isConnected()) {
      webSocket.sendBIN((uint8_t*)samples, bytes_read);
    }

    if (millis() - startTime >= 60000) {
      Serial.println("60 seconds passed. Sending END...");
      webSocket.sendTXT("END");
      recording = false;
      startTime = millis();
    }
  } else {
      Serial.println("Starting new recording...");
      recording = true;
      startTime = millis();
  }
  Serial.println("Starting new recording...");

  delay(5);
}
