#ce code represente ==> pourcentage basé sur tension instantanée = instable
#formule linéaire = peu réaliste
#pas de mémoire = sauts à chaque lancement

from ina219 import INA219, DeviceRangeError

SHUNT_OHMS = 0.1
ina = INA219(SHUNT_OHMS, address=0x40, busnum=1)
ina.configure()

def calculer_batterie():
    try:
        voltage = ina.voltage()      # V
        current = ina.current()      # mA

        # estimation simple pour LiPo 4S
        pourcentage = (voltage - 12.0) / (16.8 - 12.0) * 100
        pourcentage = max(0, min(100, pourcentage))

        if current > 0:
            autonomie_heures = (5500 * (pourcentage / 100)) / current
        else:
            autonomie_heures = 0

        print(f"Tension Batterie : {voltage:.2f} V")
        print(f"Pourcentage      : {pourcentage:.1f} %")
        print(f"Consommation     : {current:.0f} mA")
        if current > 10:
            print(f"Autonomie est.   : {autonomie_heures:.1f} h")

    except DeviceRangeError as e:
        print(f"Capteur hors plage : {e}")
    except Exception as e:
        print(f"Erreur : {e}")

calculer_batterie()