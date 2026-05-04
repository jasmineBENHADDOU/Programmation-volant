/* -------------------------------------------------
   VOLANT COMPLET 

   Comportement:
   1) Au démarrage / pas de BLE: rien ne s'allume (LEDs OFF)
   2) BLE connecté mais TTP pas validés: LEDs OFF + axes neutres + boutons relâchés
   3) Déverrouillage: TTP1 ET TTP2 doivent être détectés
   4) Après déverrouillage: toutes les LEDs en faible luminosité (DIM)
   5) Appui sur un bouton: LED associée passe à 100% (FULL), relâche => revient DIM

   Architecture:
   - LEDs sur ESP32 avec PWM (LEDC)
   - Boutons sur MCP23017 (I2C) en INPUT_PULLUP (appui = LOW)
   - 2 Hall + 2 Rollers + Joystick analog

-------------------------------------------------*/

#include <Arduino.h>
#include <BleGamepad.h>
#include "NimBLEDevice.h"
#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_MCP23X17.h>
#include <driver/ledc.h>

/* ===================== MCP23017 ===================== */
// Adresse MCP23017 si A0=A1=A2 = GND => 0x20
static const uint8_t MCP_ADDR = 0x20;

// Mapping Adafruit MCP23017:
// GPA0..7 => 0..7, GPB0..7 => 8..15
Adafruit_MCP23X17 mcp;

/* ===================== BLE ===================== */
BleGamepad bleGamepad("Dragonfly BLE Wheel", "DragonflyTeam", 100);

/* ===================== PINS  ===================== */
#define VRX_PIN      36  // joy_x (ADC input only)
#define VRY_PIN      39  // joy_y (ADC input only)

#define HALL_PIN     33  // Hall 1 (ADC)
#define HALL2_PIN    35  // Hall 2 (ADC input only)

#define ROLLER_PIN   32  // Roller 1 (ADC)
#define ROLLER2_PIN  34  // Roller 2 (ADC input only)

#define JOY_SW_PIN   15  // bouton joystick (pas de LED associée)

#define I2C_SDA_PIN  21
#define I2C_SCL_PIN  22

/* ===================== TTP223 (déverrouillage) ===================== */
// Déverrouillage UNIQUEMENT si TTP1 ET TTP2 sont actifs
// NOTE: GPIO12 est un strap pin sur certaines cartes ESP32.
// Idéalement, la sortie TTP223 doit être LOW au boot.
#define TTP1_PIN 5
#define TTP2_PIN 12
#define TTP_ACTIVE_LEVEL HIGH

static inline bool ttpUnlocked() {
  return (digitalRead(TTP1_PIN) == TTP_ACTIVE_LEVEL) &&
         (digitalRead(TTP2_PIN) == TTP_ACTIVE_LEVEL);
}

/* ===================== LEDs PWM sur ESP32 ===================== */
// 11 LEDs PWM sur ESP32 
static const uint8_t LED_PINS[11] = {4, 17, 16, 13, 23, 19, 18, 14, 25, 26, 27};
static const int LED_COUNT = 11;

// PWM LEDC
static const int PWM_FREQ = 5000;     // 5 kHz
static const int PWM_RES  = 8;        // Résolution de 8 bits, 256 valeurs possibles
static const int PWM_DIM  = 30;       // luminosité de led 
static const int PWM_FULL = 255;      // 100%

// 1 canal par LED
//static const uint8_t LED_CH[LED_COUNT] = {0,1,2,3,4,5,6,7,8,9,10};

static inline void ledsOffAll() {
  for (int i = 0; i < LED_COUNT; i++) ledcWrite(LED_PINS[i], 0);
}
static inline void ledsDimAll() {
  for (int i = 0; i < LED_COUNT; i++) ledcWrite(LED_PINS[i], PWM_DIM);
}

//luminosité des leds 
static inline void ledSet(int idx, int duty) {
  if (idx < 0 || idx >= LED_COUNT) 
  return;
  ledcWrite(LED_PINS[idx], duty);
}

/* ===================== Boutons sur MCP23017 ===================== */
// 9 boutons 
// Ici: GPA0..GPA7 (0..7) + GPB0..GPB2 (8..10)
static const uint8_t MCP_BUTTON_PINS[11] = {0,1,2,3,4,5,6,7,8,9,10};

// Mapping boutons BLE:
// - Boutons MCP -> BLE buttons 1..11
// - Joystick switch -> BLE button 13 (pas de LED associée)
static const int BLE_BTN_JOY = 13;

/* ===================== Calibration Roller  ===================== */
#define ROLLER_MIN   224
#define ROLLER_MID  1870
#define ROLLER_MAX  3760

float rollerFiltered  = 0.0f;
float roller2Filtered = 0.0f;
const int ROLLER_DEADZONE = 1500; 

/* ===================== Calibration Hall ===================== */
const int HALL_MIN = 1842;
const int HALL_MID = 1968;
const int HALL_MAX = 2027;

float hallFiltered  = 0.0f;
float hall2Filtered = 0.0f;

static bool armed = false; // devient true après TTP1+TTP2

/* ===================== Helpers sécurité (verrouillage) ===================== */
static inline void releaseAllButtons() {
  // Relâche boutons MCP (1..11)
  for (int i = 0; i < LED_COUNT; i++) {
    bleGamepad.release(i + 1);
  }
  // Relâche joystick switch
  bleGamepad.release(BLE_BTN_JOY);
}

static inline void sendNeutralAxes() {
  bleGamepad.setLeftThumb(16383, 16383); // centre
  bleGamepad.setZ(16383);
  bleGamepad.setRZ(16383);
  bleGamepad.setRX(16383);
  bleGamepad.setRY(16383);
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

  // Init PWM LEDs
  for (int i = 0; i < LED_COUNT; i++) {
    //ledcSetup(LED_CH[i], PWM_FREQ, PWM_RES);
    ledcAttach(LED_PINS[i], PWM_FREQ, PWM_RES);
  }
  ledsOffAll();

  // Boutons MCP en INPUT_PULLUP (appui = LOW)
  for (int i = 0; i < LED_COUNT; i++) {
    mcp.pinMode(MCP_BUTTON_PINS[i], INPUT_PULLUP);
  }

  // TTP223
  pinMode(TTP1_PIN, INPUT);
  pinMode(TTP2_PIN, INPUT);

  // Joystick switch
  pinMode(JOY_SW_PIN, INPUT_PULLUP);

  // Analog pins (optionnel)
  pinMode(ROLLER_PIN, INPUT);
  pinMode(ROLLER2_PIN, INPUT);
  pinMode(HALL_PIN, INPUT);
  pinMode(HALL2_PIN, INPUT);

  NimBLEDevice::setPower(ESP_PWR_LVL_N12);
  bleGamepad.begin();

  Serial.println("Gamepad BLE prêt !");
}

void loop() {
  // Pas connecté -> état repos (LEDs OFF + reset armed)
  if (!bleGamepad.isConnected()) {
    armed = false;
    ledsOffAll();
    delay(20);
    return;
  }

  // Déverrouillage TTP223: il faut LES DEUX
  if (!armed) {
    if (ttpUnlocked()) {
      armed = true;
      ledsDimAll();
      Serial.println("DEVERROUILLE: TTP1+TTP2 OK -> LEDs DIM");
    } else {

      // Toujours verrouillé
      ledsOffAll();
      releaseAllButtons();
      sendNeutralAxes();
      delay(10);
      return;
    }
  }

  /* ===================== JOYSTICK SWITCH ===================== */
  bool joyPressed = (digitalRead(JOY_SW_PIN) == LOW);
  if (joyPressed) bleGamepad.press(BLE_BTN_JOY);
  else            bleGamepad.release(BLE_BTN_JOY);

  /* ===================== BOUTONS MCP + PWM LEDs ===================== */
  // 1 bouton MCP -> 1 LED
  for (int i = 0; i < LED_COUNT; i++) {
    bool pressed = (mcp.digitalRead(MCP_BUTTON_PINS[i]) == LOW);

    // BLE boutons 1..9
    if (pressed) bleGamepad.press(i + 1);
    else         bleGamepad.release(i + 1);

    // LED associée: FULL si pressée, sinon DIM
    ledSet(i, pressed ? PWM_FULL : PWM_DIM);
  }

  /* ===================== ROLLER 1 ===================== */
  int rollerRaw = analogRead(ROLLER_PIN);
  long rollerMapped;

  if (rollerRaw >= ROLLER_MID) {
    rollerMapped = map(rollerRaw, ROLLER_MID, ROLLER_MAX, 16383, 32767);
  } else {
    rollerMapped = map(rollerRaw, ROLLER_MIN, ROLLER_MID, 0, 16383);
  }

  rollerFiltered = (rollerFiltered * 0.85f) + (rollerMapped * 0.15f);
  if (abs((int)rollerFiltered) < ROLLER_DEADZONE) rollerFiltered = 0;

  
  /* ===================== ROLLER 2 ===================== */
  int roller2Raw = analogRead(ROLLER2_PIN);
  long roller2Mapped;

  if (roller2Raw >= ROLLER_MID) {
    roller2Mapped = map(roller2Raw, ROLLER_MID, ROLLER_MAX, 16383, 32767);
  } else {
    roller2Mapped = map(roller2Raw, ROLLER_MIN, ROLLER_MID, 0, 16383);
  }

  roller2Filtered = (roller2Filtered * 0.85f) + (roller2Mapped * 0.15f);
  if (abs((int)roller2Filtered) < ROLLER_DEADZONE) roller2Filtered = 0;


  /* ===================== JOYSTICK axes ===================== */
  int vrx = analogRead(VRX_PIN);
  int vry = analogRead(VRY_PIN);

  int xValue = map(vrx, 0, 4095, 0, 32767);
  int yValue = map(vry, 0, 4095, 0, 32767);


  /* ===================== HALL 1 ===================== */
  const int NB_LECTURES = 10;
  long somme = 0;

  for (int i = 0; i < NB_LECTURES; i++) {
    somme += analogRead(HALL_PIN);
    delay(1);
  }

  int hallRaw = somme / NB_LECTURES;
  hallFiltered = 0.9f * hallFiltered + 0.1f * hallRaw;

  long steer;
  if (hallFiltered >= HALL_MID)
    steer = map((long)hallFiltered, HALL_MID, HALL_MAX, 16383, 32767);
  else
    steer = map((long)hallFiltered, HALL_MIN, HALL_MID, 0, 16383);


  /* ===================== HALL 2 ===================== */
  long somme2 = 0;

  for (int i = 0; i < NB_LECTURES; i++) {
    somme2 += analogRead(HALL2_PIN);
    delay(1);
  }

  int hall2Raw = somme2 / NB_LECTURES;
  hall2Filtered = 0.9f * hall2Filtered + 0.1f * hall2Raw;

  long steer2;
  if (hall2Filtered >= HALL_MID)
    steer2 = map((long)hall2Filtered, HALL_MID, HALL_MAX, 16383, 32767);
  else
    steer2 = map((long)hall2Filtered, HALL_MIN, HALL_MID, 0, 16383);

  
  
    /* ===================== ENVOI HID ===================== */
  bleGamepad.setLeftThumb(xValue, yValue);

  bleGamepad.setZ(steer);                 // Hall1 -> Z
  bleGamepad.setRZ(steer2);               // Hall2 -> RZ

  bleGamepad.setRX((int)rollerFiltered);  // Roller1 -> RX
  bleGamepad.setRY((int)roller2Filtered); // Roller2 -> RY

  delay(10); // ~100 Hz
}
