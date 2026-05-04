from ina219 import INA219, DeviceRangeError
import json
import os
import time

# -----------------------------
# CONFIGURATION
# -----------------------------

SHUNT_OHMS = 0.1                
BATTERY_CAPACITY_MAH = 5500     
STATE_FILE = "battery_state.json"  # fichier pour mémoriser le dernier %

# Initialisation du capteur INA219 (I2C)
ina = INA219(SHUNT_OHMS, address=0x40, busnum=1)
ina.configure()

# -----------------------------
# TABLE TENSION → POURCENTAGE
# -----------------------------
# Approximation pour batterie Li-ion 4S
# (tension, pourcentage)
VOLTAGE_TABLE_4S = [
    (16.80, 100),
    (16.40, 95),
    (16.00, 85),
    (15.60, 75),
    (15.20, 60),
    (14.80, 45),
    (14.40, 30),
    (14.00, 20),
    (13.60, 10),
    (13.20, 5),
    (12.80, 0),
]

# -----------------------------
# LECTURE / SAUVEGARDE DU % 
# -----------------------------

def load_last_percent() -> float:
    """
    Charge le dernier pourcentage enregistré.
    Permet d’éviter les sauts brutaux au démarrage.
    """
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return float(data.get("percent", 100))
        except Exception:
            pass
    return 100.0


def save_percent(percent: float) -> None:
    """
    Sauvegarde le pourcentage actuel dans un fichier JSON.
    """
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"percent": percent}, f)
    except Exception:
        pass

# -----------------------------
# CONVERSION TENSION → %
# -----------------------------

def voltage_to_percent(voltage: float) -> float:
    """
    Convertit une tension en pourcentage via interpolation.
    """
    # Cas batterie pleine
    if voltage >= VOLTAGE_TABLE_4S[0][0]:
        return 100.0

    # Cas batterie vide
    if voltage <= VOLTAGE_TABLE_4S[-1][0]:
        return 0.0

    # Parcours du tableau pour trouver l’intervalle
    for i in range(len(VOLTAGE_TABLE_4S) - 1):
        v1, p1 = VOLTAGE_TABLE_4S[i]
        v2, p2 = VOLTAGE_TABLE_4S[i + 1]

        # Si la tension est entre deux points
        if v1 >= voltage >= v2:
            # interpolation linéaire
            ratio = (voltage - v2) / (v1 - v2)
            return p2 + ratio * (p1 - p2)

    return 0.0

# -----------------------------
# MOYENNE DES MESURES
# -----------------------------

def read_average(samples: int = 8, delay: float = 0.05):
    """
    Lit plusieurs fois la tension et le courant,
    puis retourne la moyenne pour éviter le bruit.
    """
    voltages = []
    currents = []

    for _ in range(samples):
        voltages.append(ina.voltage())   # tension en V
        currents.append(ina.current())   # courant en mA
        time.sleep(delay)

    avg_voltage = sum(voltages) / len(voltages)
    avg_current = sum(currents) / len(currents)

    return avg_voltage, avg_current

# -----------------------------
# LISSAGE DU POURCENTAGE
# -----------------------------

def smooth_percent(new_percent: float, old_percent: float, max_step: float = 2.0):
    """
    Limite les variations brusques du pourcentage.
    Exemple : max ±2% par cycle.
    """
    if new_percent > old_percent + max_step:
        return old_percent + max_step
    if new_percent < old_percent - max_step:
        return old_percent - max_step
    return new_percent

# -----------------------------
# FONCTION PRINCIPALE
# -----------------------------

def calculer_batterie() -> dict:
    """
    Fonction principale qui :
    - lit le capteur
    - calcule le %
    - estime autonomie
    - retourne un dictionnaire JSON
    """
    try:
        # Lecture moyenne
        voltage, current = read_average()

        # Conversion tension → %
        raw_percent = voltage_to_percent(voltage)

        # Récupération ancienne valeur
        old_percent = load_last_percent()

        # Lissage
        percent = smooth_percent(raw_percent, old_percent)

        # Calcul puissance
        power_w = voltage * (current / 1000.0)

        # Estimation autonomie
        if current > 50:
            autonomie_heures = (BATTERY_CAPACITY_MAH * (percent / 100.0)) / current
        else:
            autonomie_heures = 0.0

        # Sauvegarde
        save_percent(percent)

        # Détection charge
        charging = current < 0

        # Retour JSON
        return {
            "status": "ok",
            "voltage": round(voltage, 2),
            "current_ma": round(current, 0),
            "percent": round(percent, 1),
            "power_w": round(power_w, 2),
            "runtime_hours": round(autonomie_heures, 1),
            "charging": charging
        }

    except DeviceRangeError as e:
        return {"status": "error", "message": str(e)}

    except Exception as e:
        return {"status": "error", "message": str(e)}