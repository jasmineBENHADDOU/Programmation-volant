import sounddevice as sd
import numpy as np
import matplotlib.pyplot as plt

# --- CONFIGURATION ---
SAMPLE_RATE = 48000
BLOCKSIZE = 2048
DEVICE = None
TARGET_MIN = 16000
TARGET_MAX = 19000
THRESHOLD = 50  # Baissé pour correspondre au format float32 standard

# --- PRÉPARATION DU GRAPHIQUE ---
plt.ion()  # Mode interactif
fig, ax = plt.subplots(figsize=(10, 5))
x_freqs = np.fft.rfftfreq(BLOCKSIZE, 1 / SAMPLE_RATE)
line, = ax.plot(x_freqs, np.zeros(len(x_freqs)), color='#11caa0', linewidth=1.5)

# Style du graphique
ax.set_xlim(0, 24000)
ax.set_title("Analyse Spectrale (FFT) - Recherche du Signal")
ax.set_xlabel("Fréquence (Hz)")
ax.set_ylabel("Amplitude FFT")
ax.grid(True, alpha=0.3)

# Zone cible colorée en arrière-plan
ax.axvspan(TARGET_MIN, TARGET_MAX, color='red', alpha=0.15, label='Zone Ultrasons (16-19 kHz)')
ax.legend(loc='upper right')

print("=== DÉMARRAGE DE L'ÉCOUTE ===")
print("Regarde à la fois le graphique et les chiffres ci-dessous :")

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
            audio = audio[:, 0].astype(np.float32)

            # 2. Calcul de la FFT
            window = np.hanning(len(audio))
            audio_win = audio * window
            fft = np.fft.rfft(audio_win)
            mag = np.abs(fft)

            # 3. Mesure de l'énergie dans la zone cible
            zone = (x_freqs >= TARGET_MIN) & (x_freqs <= TARGET_MAX)
            energy = np.max(mag[zone]) if np.any(zone) else 0

            # 4. Affichage de contrôle dans le terminal
            # Si le graphique bugge, ce print te prouvera que le micro capte bien le son
            status = " [!!! ULTRASON DÉTECTÉ !!!]" if energy > THRESHOLD else ""
            print(f"Énergie zone cible : {energy:6.2f} | Max Total : {np.max(mag):6.2f}{status}")

            # 5. MISE À JOUR EN DIRECT DU GRAPHIQUE
            line.set_ydata(mag)
            
            # --- LA LIGNE MAGIQUE POUR RECALCULER L'ÉCHELLE Y ---
            ax.relim()            # Recalcule les limites des données
            ax.autoscale_view()   # Ajuste la vue de l'axe Y automatiquement

            # Changement dynamique du titre
            if energy > THRESHOLD:
                ax.set_title(f"!!! ULTRASON DÉTECTÉ !!! (Énergie: {int(energy)})", color='red', fontweight='bold')
            else:
                ax.set_title("Analyse Spectrale (FFT) - Recherche du Signal", color='black', fontweight='normal')

            # Forcer le dessin de la fenêtre Matplotlib
            fig.canvas.draw()
            fig.canvas.flush_events()
            plt.pause(0.02)  # Laisse le temps au système de rafraîchir l'interface

except KeyboardInterrupt:
    print("\nArrêt du script.")
    plt.close()