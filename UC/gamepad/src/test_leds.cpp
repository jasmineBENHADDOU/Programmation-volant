#include <Arduino.h>

// Définition des pins
const int LED_330 = 13; 
const int LED_470 = 12;

void setup() {
    Serial.begin(115200);
    
    pinMode(LED_330, OUTPUT);
    pinMode(LED_470, OUTPUT);
    

    Serial.println("GPIO 13: 330 Ohm | GPIO 12: 470 Ohm");
}

void loop() {
    Serial.println("Démarrage du cycle de luminosité...");

    // Montée en puissance
    for (int i = 0; i <= 255; i++) {
        analogWrite(LED_330, i);
        analogWrite(LED_470, i);
        delay(15); // Vitesse du fondu
    }

    Serial.println("Luminosité Max (100%) !");
    delay(2000); // Pause à fond pour bien comparer

    // Descente en puissance
    for (int i = 255; i >= 0; i--) {
        analogWrite(LED_330, i);
        analogWrite(LED_470, i);
        delay(15);
    }

    Serial.println("Cycle terminé. Pause...");
    delay(1000);
}