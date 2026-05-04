/* -------------------------------------------------
   Dragonfly BLE Wheel (Volant COMPLET)
   - Joystick (2 axes) + bouton joystick
   - 9 boutons ESP32 -> BLE 1..9
   - 2 boutons MCP23017 -> BLE 11..12 (et LEDs associées)
   - 11 LEDs MCP
   - 2 Hall (Z et RZ)
   - 2 Roller (RX et RY)
   - 2 TTP223 : bloque tous les capteurs tant qu'aucun n'est touché
   
-------------------------------------------------*/

#include <Arduino.h>
#include <BleGamepad.h>
#include "NimBLEDevice.h"
#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_MCP23X17.h>
/* ===================== MCP23017 ===================== */
static const uint8_t MCP_ADDR = 0x20;

// 11 LEDs sur le MCP
static const uint8_t MCP_LED_PINS[] = {0,1,2,3,4,5,6,7,8,9,10};
static const int MCP_LED_COUNT = sizeof(MCP_LED_PINS) / sizeof(MCP_LED_PINS[0]);

// 2 boutons MCP
static const uint8_t MCP_BTN1_PIN = 13; // GPB5
static const uint8_t MCP_BTN2_PIN = 14; // GPB6

Adafruit_MCP23X17 mcp;

/* ===================== BLE ===================== */
BleGamepad bleGamepad("Dragonfly BLE Wheel", "DragonflyTeam", 100);

static const int BLE_BTN_MCP1 = 11;
static const int BLE_BTN_MCP2 = 12;
static const int BLE_BTN_JOY  = 13;

/* ===================== PINS ESP32 ===================== */
#define VRX_PIN     36  // joy_x
#define VRY_PIN     39  // joy_y

#define HALL1_PIN   33  // hall_y
#define HALL2_PIN   35  // hall_x 

#define ROLLER1_PIN 32
#define ROLLER2_PIN 34  

#define JOY_SW_PIN  15

#define I2C_SDA_PIN 21
#define I2C_SCL_PIN 22

/* ===================== TTP223  ===================== */

#define TTP1_PIN 23
#define TTP2_PIN 5

#define TTP_ACTIVE_LEVEL HIGH  

/* ===================== Calibration Roller ===================== */
#define ROLLER_MIN   224
#define ROLLER_MID  1870
#define ROLLER_MAX  3760

static float roller1Filtered = 0.0f;
static float roller2Filtered = 0.0f;
static const int ROLLER_DEADZONE = 1500;

/* ===================== Calibration Hall ===================== */
static const int HALL_MIN = 1842;
static const int HALL_MID = 1968;
static const int HALL_MAX = 2027;

static float hall1Filtered = 0.0f;
static float hall2Filtered = 0.0f;

/* ===================== Boutons ESP32 ===================== */
static const int extraButtonsPins[] = {13, 14, 16, 17, 18, 19, 25, 26, 27}; 
static const int extraButtonsCount = sizeof(extraButtonsPins) / sizeof(extraButtonsPins[0]);

/* -------------------------------------------------
   MCP : lit boutons -> allume LED0/LED1 + envoie BLE 11/12
------------------------------------------------- */
static inline void updateMcpButtonsAndLeds()
{
  const bool b1Pressed = (mcp.digitalRead(MCP_BTN1_PIN) == LOW);
  const bool b2Pressed = (mcp.digitalRead(MCP_BTN2_PIN) == LOW);

  mcp.digitalWrite(MCP_LED_PINS[0], b1Pressed ? HIGH : LOW);
  mcp.digitalWrite(MCP_LED_PINS[1], b2Pressed ? HIGH : LOW);

  if (b1Pressed) bleGamepad.press(BLE_BTN_MCP1);
  else           bleGamepad.release(BLE_BTN_MCP1);

  if (b2Pressed) bleGamepad.press(BLE_BTN_MCP2);
  else           bleGamepad.release(BLE_BTN_MCP2);
}

/* -------------------------------------------------
   - Active si TTP1 et TTP2 est touché (niveau HIGH)
------------------------------------------------- */
static inline bool ttpUnlocked()
{
  const int t1 = digitalRead(TTP1_PIN);
  const int t2 = digitalRead(TTP2_PIN);
  return (t1 == TTP_ACTIVE_LEVEL) && (t2 == TTP_ACTIVE_LEVEL);
}

void setup() {
  Serial.begin(115200);

  WiFi.mode(WIFI_OFF);
  btStop();

  // I2C
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);

  // MCP init
  if (!mcp.begin_I2C(MCP_ADDR, &Wire)) {
    Serial.println("ERREUR: MCP23017 non detecte !");
  } else {
    Serial.println("MCP23017 OK");
  }

  pinMode(TTP1_PIN, INPUT);
  pinMode(TTP2_PIN, INPUT);

  // LEDs MCP
  for (int i = 0; i < MCP_LED_COUNT; i++) {
    mcp.pinMode(MCP_LED_PINS[i], OUTPUT);
    mcp.digitalWrite(MCP_LED_PINS[i], LOW);
  }

  // Boutons MCP
  mcp.pinMode(MCP_BTN1_PIN, INPUT_PULLUP);
  mcp.pinMode(MCP_BTN2_PIN, INPUT_PULLUP);

  // TTP223
  pinMode(TTP1_PIN, INPUT);
  pinMode(TTP2_PIN, INPUT);

  // Joystick switch
  pinMode(JOY_SW_PIN, INPUT_PULLUP);

  // Boutons ESP32
  for (int i = 0; i < extraButtonsCount; i++) {
    pinMode(extraButtonsPins[i], INPUT_PULLUP);
  }

  // Analog
  pinMode(ROLLER1_PIN, INPUT);
  pinMode(ROLLER2_PIN, INPUT);
  pinMode(HALL1_PIN, INPUT);
  pinMode(HALL2_PIN, INPUT);

  NimBLEDevice::setPower(ESP_PWR_LVL_N12);
  bleGamepad.begin();

  Serial.println("Gamepad BLE prêt !");
}

void loop() {
  if (!bleGamepad.isConnected()) {
    delay(20);
    return;
  }

  // Toujours : boutons MCP + LEDs + boutons joystick + boutons ESP32
  updateMcpButtonsAndLeds();

  // Joystick switch -> bouton 13
  const bool joyPressed = (digitalRead(JOY_SW_PIN) == LOW);
  if (joyPressed) bleGamepad.press(BLE_BTN_JOY);
  else            bleGamepad.release(BLE_BTN_JOY);

  for (int i = 0; i < extraButtonsCount; i++) {
    const int buttonId = i + 1; // 1..9
    if (digitalRead(extraButtonsPins[i]) == LOW) bleGamepad.press(buttonId);
    else                                        
    bleGamepad.release(buttonId);
  }

  // --------- BLOQUAGE CAPTEURS ANALOG par TTP223 ---------
  if (!ttpUnlocked()) {
   
    bleGamepad.setLeftThumb(16383, 16383); // centre
    bleGamepad.setZ(16383);
    bleGamepad.setRZ(16383);
    bleGamepad.setRX(16383);
    bleGamepad.setRY(16383);

    delay(10);
    return;
  }

  /* ------------------ JOYSTICK axes ------------------ */
  const int vrx = analogRead(VRX_PIN);
  const int vry = analogRead(VRY_PIN);
  const int xValue = map(vrx, 0, 4095, 0, 32767);
  const int yValue = map(vry, 0, 4095, 0, 32767);
  bleGamepad.setLeftThumb(xValue, yValue);

  /* ------------------ ROLLER 1 -> RX ------------------ */
  const int roller1Raw = analogRead(ROLLER1_PIN);
  long roller1Mapped;

  if (roller1Raw >= ROLLER_MID)
    roller1Mapped = map(roller1Raw, ROLLER_MID, ROLLER_MAX, 16383, 32767);
  else
    roller1Mapped = map(roller1Raw, ROLLER_MIN, ROLLER_MID, 0, 16383);

  roller1Filtered = (roller1Filtered * 0.85f) + (roller1Mapped * 0.15f);
  if (abs((int)roller1Filtered) < ROLLER_DEADZONE) roller1Filtered = 0;
  bleGamepad.setRX((int)roller1Filtered);

  /* ------------------ ROLLER 2 -> RY ------------------ */
  const int roller2Raw = analogRead(ROLLER2_PIN);
  long roller2Mapped;

  if (roller2Raw >= ROLLER_MID)
    roller2Mapped = map(roller2Raw, ROLLER_MID, ROLLER_MAX, 16383, 32767);
  else
    roller2Mapped = map(roller2Raw, ROLLER_MIN, ROLLER_MID, 0, 16383);

  roller2Filtered = (roller2Filtered * 0.85f) + (roller2Mapped * 0.15f);
  if (abs((int)roller2Filtered) < ROLLER_DEADZONE) roller2Filtered = 0;
  bleGamepad.setRY((int)roller2Filtered);

  /* ------------------ HALL 1 -> Z ------------------ */
  const int NB_LECTURES = 10;
  long somme1 = 0;
  for (int i = 0; i < NB_LECTURES; i++) {
    somme1 += analogRead(HALL1_PIN);
    delay(1);
  }
  const int hall1Raw = somme1 / NB_LECTURES;
  hall1Filtered = 0.9f * hall1Filtered + 0.1f * hall1Raw;

  long steer1;
  if (hall1Filtered >= HALL_MID)
    steer1 = map((long)hall1Filtered, HALL_MID, HALL_MAX, 16383, 32767);
  else
    steer1 = map((long)hall1Filtered, HALL_MIN, HALL_MID, 0, 16383);

  bleGamepad.setZ(steer1);

  /* ------------------ HALL 2 -> RZ ------------------ */
  long somme2 = 0;
  for (int i = 0; i < NB_LECTURES; i++) {
    somme2 += analogRead(HALL2_PIN);
    delay(1);
  }
  const int hall2Raw = somme2 / NB_LECTURES;
  hall2Filtered = 0.9f * hall2Filtered + 0.1f * hall2Raw;

  long steer2;
  if (hall2Filtered >= HALL_MID)
    steer2 = map((long)hall2Filtered, HALL_MID, HALL_MAX, 16383, 32767);
  else
    steer2 = map((long)hall2Filtered, HALL_MIN, HALL_MID, 0, 16383);

  bleGamepad.setRZ(steer2);

  delay(10);
}
