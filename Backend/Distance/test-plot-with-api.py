# Test de visualisation en temps réel du spectre audio + API WebSocket
# Objectif :
# - garder le graphique Matplotlib de test-plot.py
# - ajouter la partie API/WebSocket de test-plot-api.py
# - envoyer en temps réel l'énergie FFT vers l'interface HTML

import sounddevice as sd
import numpy as np
import matplotlib.pyplot as plt
import threading
import json
import time
from flask import Flask, jsonify
from flask_sock import Sock

# --- CONFIGURATION AUDIO ---
SAMPLE_RATE = 48000
BLOCKSIZE = 2048
DEVICE = None

# Vos réglages validés sur le terrain : cible calée sur le sifflement à 11 kHz
TARGET_MIN = 11000
TARGET_MAX = 14000

# Paramètres de sensibilité et d'amortissement ajustés
THRESHOLD = 1.5       # Seuil bas adapté au signal lointain
SMOOTH_ALPHA = 0.5    # Amortissement idéal pour un radar visuel fluide
SOFTWARE_GAIN = 15.0   # Ton amplificateur logiciel réglé à 8 !

# --- CONFIGURATION API / WEBSOCKET ---
app = Flask(__name__)
sock = Sock(app)

clients = set()
clients_lock = threading.Lock()

# Dernière valeur calculée, lisible par l'API et envoyée au frontend
latest = {
    "energy": 0.0,
    "detected": False,
    "distance_cm": None,
    "target_min": TARGET_MIN,
    "target_max": TARGET_MAX
}

# --- CALIBRATION DISTANCE OPTIONNELLE ---
CAL_NEAR_ENERGY = None
CAL_NEAR_CM = 30
CAL_FAR_ENERGY = None
CAL_FAR_CM = 150

def energy_to_distance(energy):
    if CAL_NEAR_ENERGY is None or CAL_FAR_ENERGY is None:
        return None

    log_near = np.log(max(CAL_NEAR_ENERGY, 1e-9))
    log_far = np.log(max(CAL_FAR_ENERGY, 1e-9))
    log_e = np.log(max(energy, 1e-9))

    t = (log_e - log_near) / (log_far - log_near + 1e-9)
    dist = CAL_NEAR_CM + t * (CAL_FAR_CM - CAL_NEAR_CM)

    return float(np.clip(dist, CAL_NEAR_CM * 0.5, CAL_FAR_CM * 1.5))


def send_to_clients(data):
    msg = json.dumps(data)
    dead = set()

    with clients_lock:
        for ws in clients:
            try:
                ws.send(msg)
            except Exception:
                dead.add(ws)

        clients.difference_update(dead)


# --- API HTTP SIMPLE ---

# --- ROUTE POUR SERVIR LA PAGE RADAR ---
@app.route("/", methods=["GET"])
def index():
    """
    Lit le fichier HTML et l'envoie directement au navigateur
    """
    try:
        # Remplace bien par le nom exact de ton fichier HTML s'il change
        with open("6_Distance.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Erreur : Impossible de lire le fichier HTML ({str(e)})", 500


@app.route("/distance", methods=["GET"])
def get_distance():
    return jsonify(latest)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "ultrasonic-distance-api"})


# --- WEBSOCKET ---
@sock.route("/ws")
def ws_handler(ws):
    with clients_lock:
        clients.add(ws)

    print("Client WebSocket connecté")

    try:
        while True:
            ws.receive(timeout=60)
    except Exception:
        pass
    finally:
        with clients_lock:
            clients.discard(ws)
        print("Client WebSocket déconnecté")


def run_api():
    print("API HTTP : http://0.0.0.0:5000/distance")
    print("WebSocket : ws://0.0.0.0:5000/ws")
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


# --- PRÉPARATION DU GRAPHIQUE ---
plt.ion()
fig, ax = plt.subplots(figsize=(10, 5))

x_freqs = np.fft.rfftfreq(BLOCKSIZE, 1 / SAMPLE_RATE)
line, = ax.plot(x_freqs, np.zeros(len(x_freqs)), color="#11caa0", linewidth=1.5)

ax.set_xlim(0, 24000)
ax.set_ylim(0, 10)
ax.set_title("Analyse Spectrale (FFT) - Recherche du Signal")
ax.set_xlabel("Fréquence (Hz)")
ax.set_ylabel("Amplitude FFT")
ax.grid(True, alpha=0.3)

ax.axvspan(
    TARGET_MIN,
    TARGET_MAX,
    color="red",
    alpha=0.15,
    label=f"Zone cible ({TARGET_MIN}-{TARGET_MAX} Hz)"
)
ax.legend(loc="upper right")

prev_energy = 0.0
prev_mag = np.zeros(len(x_freqs), dtype=float)

print("=== DÉMARRAGE DE L'ÉCOUTE ===")

# Lancement API/WebSocket en arrière-plan
api_thread = threading.Thread(target=run_api, daemon=True)
api_thread.start()

try:
    with sd.InputStream(
        device=DEVICE,
        samplerate=SAMPLE_RATE,
        channels=2,
        dtype="float32",
        blocksize=BLOCKSIZE
    ) as stream:

        while True:
            # 1. Lecture du flux audio
            audio, overflowed = stream.read(BLOCKSIZE)

            if overflowed:
                print("Attention : input overflow")

            audio = audio[:, 0].astype(np.float32)

            # 2. Calcul FFT + Amplification logicielle
            window = np.hanning(len(audio))
            audio_win = audio * window
            fft = np.fft.rfft(audio_win)
            mag = np.abs(fft)
            
            # Application de ton gain à 8 !
            mag = mag * SOFTWARE_GAIN

            # 3. Énergie dans la zone cible
            zone = (x_freqs >= TARGET_MIN) & (x_freqs <= TARGET_MAX)
            energy = np.max(mag[zone]) if np.any(zone) else 0.0

            # 4. Lissage EMA
            smoothed_mag = SMOOTH_ALPHA * mag + (1 - SMOOTH_ALPHA) * prev_mag
            smoothed_energy = SMOOTH_ALPHA * energy + (1 - SMOOTH_ALPHA) * prev_energy

            prev_mag = smoothed_mag
            prev_energy = smoothed_energy

            # 5. Détection
            detected = smoothed_energy > THRESHOLD
            distance_cm = energy_to_distance(smoothed_energy)

            # 6. Mise à jour des valeurs API
            latest["energy"] = round(float(smoothed_energy), 4)
            latest["detected"] = bool(detected)
            latest["distance_cm"] = round(distance_cm, 1) if distance_cm is not None else None
            latest["target_min"] = TARGET_MIN
            latest["target_max"] = TARGET_MAX

            # 7. Envoi WebSocket en direct vers ton HTML
            send_to_clients(latest)

            # 8. Affichage terminal
            status = " [!!! SIGNAL DÉTECTÉ !!!]" if detected else ""
            print(
                f"Énergie zone cible (lissée): {smoothed_energy:6.2f} | "
                f"Max Total : {np.max(mag):6.2f}{status}"
            )

            # 9. Mise à jour du graphique
            line.set_ydata(smoothed_mag)

            # --- RECALCUL DYNAMIQUE DE L'AXE Y ---
            ax.relim()            # Recalcule les limites selon le signal amplifié
            ax.autoscale_view()   # Ajuste la vue de l'axe Y automatiquement

            if detected:
                ax.set_title(
                    f"!!! SIGNAL DÉTECTÉ !!! (Énergie: {int(smoothed_energy)})",
                    color="red",
                    fontweight="bold"
                )
            else:
                ax.set_title("Analyse Spectrale (FFT) - Recherche du Signal", color="black", fontweight="normal")

            fig.canvas.draw()
            fig.canvas.flush_events()
            plt.pause(0.02)

except KeyboardInterrupt:
    print("\nArrêt du script.")
    plt.close()