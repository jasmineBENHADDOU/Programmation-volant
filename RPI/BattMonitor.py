from ina219 import INA219, DeviceRangeError
import time

SHUNT_OHMS = 0.1
BATTERY_CAPACITY_MAH = 5500

VOLTAGE_TABLE_4S = [
    (16.80, 100),
    (16.56, 95),
    (16.40, 90),
    (16.16, 85),
    (15.92, 75),
    (15.60, 65),
    (15.20, 55),
    (14.80, 45),
    (14.40, 30),
    (14.00, 20),
    (13.60, 12),
    (13.20, 6),
    (12.80, 2),
    (12.00, 0),
]


def voltage_to_percent(voltage: float) -> float:
    if voltage >= VOLTAGE_TABLE_4S[0][0]:
        return 100.0

    if voltage <= VOLTAGE_TABLE_4S[-1][0]:
        return 0.0

    for i in range(len(VOLTAGE_TABLE_4S) - 1):
        v1, p1 = VOLTAGE_TABLE_4S[i]
        v2, p2 = VOLTAGE_TABLE_4S[i + 1]

        if v1 >= voltage >= v2:
            ratio = (voltage - v2) / (v1 - v2)
            return round(p2 + ratio * (p1 - p2), 1)

    return 0.0


def get_ina219():
    ina = INA219(
        SHUNT_OHMS,
        address=0x40,
        busnum=1
    )

    ina.configure()

    return ina


def read_average(ina, samples: int = 8, delay: float = 0.05):
    voltages = []
    currents = []

    for _ in range(samples):
        try:
            voltages.append(ina.voltage())
            currents.append(ina.current())

        except DeviceRangeError:
            pass

        time.sleep(delay)

    if not voltages:
        raise RuntimeError("Aucune lecture INA219 valide")

    voltage = sum(voltages) / len(voltages)
    current = sum(currents) / len(currents)

    return voltage, current


def calculer_batterie():
    try:
        # On tente de se connecter à l'INA219 à chaque appel.
        # Ainsi, si le capteur est branché après le démarrage,
        # il sera automatiquement détecté.
        ina = get_ina219()

        voltage, current = read_average(ina)

        percent = voltage_to_percent(voltage)

        power_w = voltage * (current / 1000.0)

        # Courant positif = consommation.
        if current > 50:
            runtime_hours = (
                BATTERY_CAPACITY_MAH
                * (percent / 100.0)
            ) / current
        else:
            runtime_hours = 0.0

        # Selon le sens de branchement de ton INA219,
        # un courant négatif correspond ici à une charge.
        charging = current < -50

        return {
            "status": "ok",
            "voltage": round(voltage, 2),
            "current_ma": round(current, 0),
            "percent": round(percent, 1),
            "power_w": round(power_w, 2),
            "runtime_hours": round(runtime_hours, 1),
            "charging": charging
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "percent": 0,
            "charging": False
        }


if __name__ == "__main__":
    import json

    while True:
        result = calculer_batterie()

        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False
            )
        )

        time.sleep(1)