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
SMOOTH_ALPHA = 0.3  # Coefficient d'EMA (0->pas de lissage, 1->pas d'historique)

# --- PRÉPARATION DU GRAPHIQUE ---
plt.ion()  # Mode interactif
fig, ax = plt.subplots(figsize=(10, 5))
x_freqs = np.fft.rfftfreq(BLOCKSIZE, 1 / SAMPLE_RATE)
line, = ax.plot(x_freqs, np.zeros(len(x_freqs)), color='#11caa0', linewidth=1.5)

# Style du graphique
ax.set_xlim(0, 24000)
ax.set_ylim(0,10)
ax.set_title("Analyse Spectrale (FFT) - Recherche du Signal")
ax.set_xlabel("Fréquence (Hz)")
ax.set_ylabel("Amplitude FFT")
ax.grid(True, alpha=0.3)

# Zone cible colorée en arrière-plan
ax.axvspan(TARGET_MIN, TARGET_MAX, color='red', alpha=0.15, label='Zone Ultrasons (16-19 kHz)')
ax.legend(loc='upper right')

# États pour le lissage exponentiel (EMA)
prev_energy = 0.0
prev_mag = np.zeros(len(x_freqs), dtype=float)

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
            window = np.hanning(len(audio))     #génère un vecteur de coefficients de pondération qui commence et finit à zéro et est plus fort au milieu
            audio_win = audio * window
            fft = np.fft.rfft(audio_win)
            mag = np.abs(fft)

            # 3. Mesure de l'énergie dans la zone cible
            zone = (x_freqs >= TARGET_MIN) & (x_freqs <= TARGET_MAX)
            energy = np.max(mag[zone]) if np.any(zone) else 0

            # Appliquer un lissage exponentiel (EMA) sur le spectre et l'énergie
            smoothed_mag = SMOOTH_ALPHA * mag + (1 - SMOOTH_ALPHA) * prev_mag
            smoothed_energy = SMOOTH_ALPHA * energy + (1 - SMOOTH_ALPHA) * prev_energy

            # Mettre à jour les états pour la prochaine itération
            prev_mag = smoothed_mag
            prev_energy = smoothed_energy

            # 4. Affichage de contrôle dans le terminal
            # Si le graphique bugge, ce print te prouvera que le micro capte bien le son
            status = " [!!! ULTRASON DÉTECTÉ !!!]" if smoothed_energy > THRESHOLD else ""
            print(f"Énergie zone cible (lissée): {smoothed_energy:6.2f} | Max Total : {np.max(mag):6.2f}{status}")

            # 5. MISE À JOUR EN DIRECT DU GRAPHIQUE
            # Afficher le spectre lissé pour réduire le bruit visuel
            line.set_ydata(smoothed_mag)
            
            # --- LA LIGNE MAGIQUE POUR RECALCULER L'ÉCHELLE Y ---
            # ax.relim()            # Recalcule les limites des données
            # ax.autoscale_view()   # Ajuste la vue de l'axe Y automatiquement

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
