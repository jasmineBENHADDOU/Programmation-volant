# Architecture batterie Dragonfly V2

## Objectif

Afficher dynamiquement l'état de la batterie 4S du Dragonfly sur l'interface utilisateur affichée sur l'écran HDMI du Raspberry Pi 5.

---

## Architecture générale

```
Batterie 4S
   ↓
INA219
   ↓
Python (battery_monitor.py)
   ↓
API locale Flask (api_server.py)
   ↓
Frontend HTML / CSS / JavaScript
   ↓
Écran HDMI Raspberry Pi
```
