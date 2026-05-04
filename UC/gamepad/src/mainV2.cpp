/* -------------------------------------------------
   Joystick + 12 bouton + 2 Hall + 2 Roller + 2 tactil sensors + 12 leds  = Volant COMPLET
-------------------------------------------------*/

#include <Arduino.h>
#include <BleGamepad.h>
#include "NimBLEDevice.h"
#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_MCP23X17.h>

// Adresse MCP23017 si A0=A1=A2 = GND => 0x20
static const uint8_t MCP_ADDR = 0x20;

static const uint8_t MCP_LED_PINS[12] = {0,1,2,3,4,5,6,7,8,9,10,11};  // 12 LEDs sur le MCP : GPA0..GPA7 (=0..7) + GPB0..GPB3 (=8..11) , on aura besoin que de 11 leds


// Mapping Adafruit:          GPA0..7 => 0..7,       GPB0..7 => 8..15

static const uint8_t MCP_BTN1_PIN = 13; // 13 correspond à GPB5 , ceci designe 2 boutons classique  et celui la est bg_h
static const uint8_t MCP_BTN2_PIN = 14; // GPB6 et celui la est BG_M


Adafruit_MCP23X17 mcp;


/*static inline void updateMcpLedsFromButtons()
{
  // Boutons en pull-up => appui = LOW
  bool b1Pressed = (mcp.digitalRead(MCP_BTN1_PIN) == LOW);
  bool b2Pressed = (mcp.digitalRead(MCP_BTN2_PIN) == LOW);

  // Mode "momentane" : LED allumee tant que tu appuies
  mcp.digitalWrite(MCP_LED_PINS[BTN1_LED_INDEX], b1Pressed ? HIGH : LOW);
  mcp.digitalWrite(MCP_LED_PINS[BTN2_LED_INDEX], b2Pressed ? HIGH : LOW);
} */


#define VRX_PIN     36  //joy_x
#define VRY_PIN     39 //joy_y 
#define HALL_PIN    33     //hall_y 
#define ROLLER_PIN  32   

#define I2C_SDA_PIN 21
#define I2C_SCL_PIN 22

//#define ROLLER2_PIN  34
//#define HALL2_PIN    35   //hall_x

// --- Calibration Roller ---
#define ROLLER_MIN   224
#define ROLLER_MID  1870
#define ROLLER_MAX  3760

float rollerFiltered = 0;
//float roller2Filtered = 0;   
const int ROLLER_DEADZONE = 1500;

// --- Calibration Hall monté sur le systeme ---
const int HALL_MIN = 1842;
const int HALL_MID = 1968;
const int HALL_MAX = 2027;


float hallFiltered = 0;
//float hall2Filtered = 0;     

const int extraButtonsPins[10] = {4, 13, 14, 16, 17, 18, 19, 25, 26, 27}; //enlever 12 et 15 et LES METTTRE AVEC MCP  

const int extraButtonsCount = 10;

// --- BLE Gamepad ---
BleGamepad bleGamepad("Dragonfly BLE Wheel", "DragonflyTeam", 100);

void setup() {

  Wire1.begin(I2C_SDA_PIN, I2C_SCL_PIN, 100000);

  Serial.begin(115200);

    WiFi.mode(WIFI_OFF);     
    btStop();                
    
    Wire.begin(); // ESP32: SDA=21, SCL=22 par defaut

  if (!mcp.begin_I2C(MCP_ADDR, &Wire)) {
    Serial.println("ERREUR: MCP23017 non detecte !");
  } else {
    Serial.println("MCP23017 OK");
  } 

  // Configure 12 LEDs en sortie et eteint tout
  for (int i = 0; i < 12; i++) {
    mcp.pinMode(MCP_LED_PINS[i], OUTPUT);
    mcp.digitalWrite(MCP_LED_PINS[i], LOW);
  }

  // Configure les 2 boutons en entree + pull-up
  mcp.pinMode(MCP_BTN1_PIN, INPUT_PULLUP);
  mcp.pinMode(MCP_BTN2_PIN, INPUT_PULLUP);


  // Boutons : pull-up pour éviter les flottements sur pins non branchés
  for (int i = 0; i < extraButtonsCount; i++) {
    pinMode(extraButtonsPins[i], INPUT_PULLUP);
  }


  pinMode(ROLLER_PIN, INPUT);
  pinMode(HALL_PIN, INPUT);

  NimBLEDevice::setPower(ESP_PWR_LVL_N12);   // plus faible = -12 dBm

  bleGamepad.begin();

  Serial.println("Gamepad BLE prêt !");
}

void loop() {

  //updateMcpLedsFromButtons();

  if (bleGamepad.isConnected()) {

    /* ------------------ ROLLER 1 ------------------ */

    int rollerRaw = analogRead(ROLLER_PIN);
    long rollerMapped;

    if (rollerRaw >= ROLLER_MID)
    {
        rollerMapped = map(rollerRaw,
                           ROLLER_MID, ROLLER_MAX,
                           16383, 32767);
    }
    else
    {
        rollerMapped = map(rollerRaw,
                           ROLLER_MIN, ROLLER_MID,
                           0, 16383);
    }

    rollerFiltered = (rollerFiltered * 0.85) + (rollerMapped * 0.15);

    if (abs(rollerFiltered) < 1500)
        rollerFiltered = 0;


    /* ------------------ ROLLER 2------------------

    int roller2Raw = analogRead(ROLLER2_PIN);
    long roller2Mapped;

    if (roller2Raw >= ROLLER_MID)
    {
        roller2Mapped = map(roller2Raw,
                            ROLLER_MID, ROLLER_MAX,
                            16383, 32767);
    }
    else
    {
        roller2Mapped = map(roller2Raw,
                            ROLLER_MIN, ROLLER_MID,
                            0, 16383);
    }

    roller2Filtered = (roller2Filtered * 0.85) + (roller2Mapped * 0.15);

    if (abs(roller2Filtered) < 1500)
        roller2Filtered = 0;


    /* ------------------ JOYSTICK  ------------------ */

    int vrx = analogRead(VRX_PIN);
    int vry = analogRead(VRY_PIN);
    
    int xValue = map(vrx, 0, 4095, 0, 32767);
    int yValue = map(vry, 0, 4095, 0, 32767);


    /* ------------------ HALL 1  ------------------ */

    const int NB_LECTURES = 10;
    long somme = 0;

    for (int i = 0; i < NB_LECTURES; i++) {
      somme += analogRead(HALL_PIN);
      delay(1);
    }

    int hallRaw = somme / NB_LECTURES;
    hallFiltered = 0.9 * hallFiltered + 0.1 * hallRaw;

    long steer;
    if (hallFiltered >= HALL_MID)
      steer = map(hallFiltered, HALL_MID, HALL_MAX, 16383, 32767);
    else
      steer = map(hallFiltered, HALL_MIN, HALL_MID, 0, 16383);


    /* ------------------ HALL 2 ------------------ 

    long somme2 = 0;

    for (int i = 0; i < NB_LECTURES; i++) {
      somme2 += analogRead(HALL2_PIN);
      delay(1);
    }

    int hall2Raw = somme2 / NB_LECTURES;
    hall2Filtered = 0.9 * hall2Filtered + 0.1 * hall2Raw;

    long steer2;
    if (hall2Filtered >= HALL_MID)
      steer2 = map(hall2Filtered, HALL_MID, HALL_MAX, 0, 32767);
    else
      steer2 = map(hall2Filtered, HALL_MIN, HALL_MID, -32767, 0);


    /* ------------------ ENVOI HID ------------------ */

    bleGamepad.setLeftThumb(xValue, yValue);
    bleGamepad.setZ(steer);
    bleGamepad.setRX((int)rollerFiltered);

   // bleGamepad.setRY((int)roller2Filtered); // roller 2
    //bleGamepad.setRZ(steer2);               // hall 2


    /* ------------------ BOUTONS ------------------ */

  for (int i = 0; i < extraButtonsCount; i++) {
    int buttonId = i + 1; // 1..12
    if (digitalRead(extraButtonsPins[i]) == LOW) bleGamepad.press(buttonId);
    else bleGamepad.release(buttonId);
  }

    // Debug Serial

    //Serial.printf("Hall = %d | HallFiltered = %.2f | ROLLER1=%d | MAP1=%ld\n", hallRaw, hallFiltered, rollerRaw, rollerMapped);

    delay(10); // ~100 Hz

  }

}
