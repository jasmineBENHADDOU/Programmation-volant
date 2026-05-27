""" La durée du chirp affecte directement l'amplitude du peak (corrélation).

Pourquoi : Plus le chirp est long, plus il y a d'échantillons à corréler, donc plus l'énergie s'accumule dans le pic de corrélation.

Exemple simplifié :

Chirp 20ms (~960 échantillons) → petite corrélation → peak ≈ 0.01-0.06 (trop faible)
Chirp 100ms (~4800 échantillons) → grosse corrélation → peak ≈ 5-50 (détectable) """

import sounddevice as sd
import numpy as np
import time

SAMPLE_RATE = 48000 # frequence d'echantillonage 
BLOCKSIZE = 2048
DEVICE = None

TARGET_MIN = 15000
TARGET_MAX = 18000
THRESHOLD = 1  # à ajuster après test

# --- Chirp template for matched filter detection ---
def make_chirp(fs, f0=10000, f1=15000, duration=0.1):
    t = np.linspace(0, duration, int(fs * duration), endpoint=False)
    phi = 2 * np.pi * (f0 * t + 0.5 * (f1 - f0) / duration * t ** 2)
    return np.sin(phi).astype(np.float32)

template = make_chirp(SAMPLE_RATE, 10000, 15000, 0.4)
# Normaliser le template par son énergie pour amplifier la corrélation
template = template / (np.linalg.norm(template) + 1e-6)
template_rev = template[::-1]
print(f"Chirp template: 10000-15000 Hz, durée 0.4s, DEVICE={DEVICE}")
print("Écoute ...")

with sd.InputStream(
    device=DEVICE,
    samplerate=SAMPLE_RATE,
    channels=2,     # 2 canaux (stéréo : gauche + droite)
    dtype="float32",
    blocksize=BLOCKSIZE   # Lit 2048 échantillons à la fois
) as stream:

    while True:
        audio, overflowed = stream.read(BLOCKSIZE)

        #if overflowed:
            #print("overflow")

        audio = audio[:, 0].astype(np.float32)

        # Matched filter / cross-correlation with the known chirp
        # (Hanning window removed temporarily for testing)
        corr = np.abs(np.convolve(audio, template_rev, mode='valid'))
        if corr.size == 0:
            continue
        peak = np.max(corr)
        idx = int(np.argmax(corr))

        # Robust noise estimate (MAD) and adaptive threshold
        med = np.median(corr)
        mad = np.median(np.abs(corr - med))
        noise_est = mad * 1.4826
        adaptive_threshold = max(THRESHOLD, med + 6 * noise_est)

        # Debug print (comment/uncomment if needed)
        med_corr = np.mean(corr) if corr.size > 0 else 0
        print(f"peak={peak:.2f} median_corr={med_corr:.2f} thr={adaptive_threshold:.2f}")
        if peak > adaptive_threshold:
            print(f"peak={peak:.2f} thr={adaptive_threshold:.2f}")

        if peak > adaptive_threshold:
            t_detect = time.time()
            arrival_sec = idx / SAMPLE_RATE
            print(f"ULTRASON DETECTE peak={int(peak)} idx={idx} t+{arrival_sec:.4f}s time={t_detect}")
            time.sleep(0.1)
        else:
            # faible charge CPU quand rien détecté
            time.sleep(0.05)
