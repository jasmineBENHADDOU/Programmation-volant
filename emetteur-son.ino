const int boutonPin = 2;   // Le bouton est sur la broche 2
const int signalPin = 6;   // Ton haut-parleur (transistor) est sur la broche 6

bool sonActif = false;     // Au démarrage, le son est ÉTEINT

void setup() {
  // On dit à l'Arduino que la broche 2 attend un bouton et on active sa résistance interne
  pinMode(boutonPin, INPUT_PULLUP); 
}

void loop() {
  // Si on détecte un appui sur le bouton (la broche passe à BAS / LOW)
  if (digitalRead(boutonPin) == LOW) {
    
    sonActif = !sonActif; // On inverse l'état : si c'était vrai, ça devient faux, et vice-versa
    
    if (sonActif) {
      tone(signalPin, 14000);  // On allume le sifflement à 16 kHz
    } else {
      noTone(signalPin);       // On coupe proprement le sifflement
    }
    
    delay(300); // Petite pause "anti-double clic" pour laisser le temps de relâcher le bouton
  }
}