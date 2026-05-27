"""
RPi_recepteur.py — Détection chirp 15-16 kHz + estimation distance en cm
SPH0645 via I2S

AVANT DE LANCER :
  - Branche SEL sur GND (canal gauche garanti)
  - Lance PC_emetteur.py sur le PC

UTILISATION :
  1. Lance le script → phase de calibration automatique (bruit de fond, 3s)
  2. Mets-toi à 30 cm du PC → appuie sur Entrée
  3. Mets-toi à 150 cm du PC → appuie sur Entrée
  4. La distance s'affiche en temps réel
"""

import sounddevice as sd
import numpy as np
import time
import threading

# ── Paramètres — identiques à PC_emetteur.py ────────────────────────────
SAMPLE_RATE   = 48000
BLOCKSIZE     = 4096
DEVICE        = None      # None = défaut ALSA, ou mettre l'index (arecord -l)

CHIRP_F0      = 15000
CHIRP_F1      = 16000
CHIRP_DUR     = 0.2

FFT_BAND_LOW  = 14800
FFT_BAND_HIGH = 16200

# ── Template chirp ───────────────────────────────────────────────────────
def make_chirp(fs, f0, f1, duration):
    t   = np.linspace(0, duration, int(fs * duration), endpoint=False)
    phi = 2 * np.pi * (f0 * t + 0.5 * (f1 - f0) / duration * t**2)
    sig = np.sin(phi).astype(np.float32)
    sig *= np.hanning(len(sig)).astype(np.float32)
    return sig / (np.linalg.norm(sig) + 1e-9)

template     = make_chirp(SAMPLE_RATE, CHIRP_F0, CHIRP_F1, CHIRP_DUR)
template_rev = template[::-1]
print(f"Template : {CHIRP_F0/1000:.0f}–{CHIRP_F1/1000:.0f} kHz | {len(template)} échantillons")

# ── Variables de calibration ─────────────────────────────────────────────
cal_near_peak  = None   # peak à distance proche (30 cm)
cal_far_peak   = None   # peak à distance loin (150 cm)
NEAR_CM        = 30
FAR_CM         = 150

enter_pressed  = threading.Event()

def wait_enter():
    input()
    enter_pressed.set()


def read_audio_block(stream):
    """Lit un bloc, convertit int32→float32, retourne le canal gauche."""
    block, overflowed = stream.read(BLOCKSIZE)
    if overflowed:
        print("⚠️  Overflow")
    audio = block[:, 0].astype(np.float64) / 2**31
    return audio.astype(np.float32)


def measure_peak(stream, duration=1.0):
    """Mesure le peak de corrélation moyen sur `duration` secondes."""
    peaks = []
    n_blocks = max(1, int(SAMPLE_RATE * duration / BLOCKSIZE))
    for _ in range(n_blocks):
        audio = read_audio_block(stream)
        window = np.hanning(len(audio))
        fft    = np.fft.rfft(audio * window)
        freqs  = np.fft.rfftfreq(len(audio), 1 / SAMPLE_RATE)
        mag    = np.abs(fft)
        zone   = (freqs >= FFT_BAND_LOW) & (freqs <= FFT_BAND_HIGH)
        energy = float(np.max(mag[zone]))
        if energy > fft_threshold:
            corr = np.abs(np.convolve(audio, template_rev, mode='valid'))
            if corr.size > 0:
                peaks.append(float(np.max(corr)))
    return float(np.mean(peaks)) if peaks else 0.0


def peak_to_distance(peak):
    """Convertit un peak de corrélation en distance (cm) par interpolation log."""
    if cal_near_peak is None or cal_far_peak is None:
        return None
    if peak <= 0:
        return FAR_CM
    # Loi acoustique : peak ∝ 1/d² → log(peak) linéaire en log(d)
    log_near = np.log(max(cal_near_peak, 1e-9))
    log_far  = np.log(max(cal_far_peak,  1e-9))
    log_peak = np.log(max(peak, 1e-9))
    # Interpolation
    t = (log_peak - log_near) / (log_far - log_near + 1e-9)
    dist = NEAR_CM + t * (FAR_CM - NEAR_CM)
    return float(np.clip(dist, NEAR_CM * 0.5, FAR_CM * 1.5))


# ── Ouverture flux ───────────────────────────────────────────────────────
print(f"\nOuverture flux audio (int32, stéréo, fs={SAMPLE_RATE})…")

with sd.InputStream(
    device     = DEVICE,
    samplerate = SAMPLE_RATE,
    channels   = 2,
    dtype      = "int32",
    blocksize  = BLOCKSIZE,
) as stream:

    # ── ÉTAPE 1 : Calibration bruit de fond ─────────────────────────────
    print("\n── CALIBRATION BRUIT DE FOND (3s) ──")
    print("Reste silencieux, PC_emetteur.py doit tourner…")
    cal_energies = []
    for _ in range(int(SAMPLE_RATE * 3 / BLOCKSIZE)):
        audio  = read_audio_block(stream)
        window = np.hanning(len(audio))
        fft    = np.fft.rfft(audio * window)
        freqs  = np.fft.rfftfreq(len(audio), 1 / SAMPLE_RATE)
        mag    = np.abs(fft)
        zone   = (freqs >= FFT_BAND_LOW) & (freqs <= FFT_BAND_HIGH)
        cal_energies.append(float(np.max(mag[zone])))

    noise_floor   = np.mean(cal_energies)
    noise_std     = np.std(cal_energies)
    fft_threshold = noise_floor + 5 * noise_std
    print(f"Bruit de fond : mean={noise_floor:.5f}  std={noise_std:.5f}")
    print(f"Seuil FFT     : {fft_threshold:.5f}")

    # ── ÉTAPE 2 : Calibration distance proche ───────────────────────────
    print(f"\n── CALIBRATION PROCHE ({NEAR_CM} cm) ──")
    print(f"Place-toi à {NEAR_CM} cm du PC, puis appuie sur Entrée…")
    enter_pressed.clear()
    t = threading.Thread(target=wait_enter, daemon=True)
    t.start()
    enter_pressed.wait()
    cal_near_peak = measure_peak(stream, duration=2.0)
    print(f"Peak à {NEAR_CM} cm : {cal_near_peak:.5f}")

    # ── ÉTAPE 3 : Calibration distance loin ─────────────────────────────
    print(f"\n── CALIBRATION LOIN ({FAR_CM} cm) ──")
    print(f"Place-toi à {FAR_CM} cm du PC, puis appuie sur Entrée…")
    enter_pressed.clear()
    t = threading.Thread(target=wait_enter, daemon=True)
    t.start()
    enter_pressed.wait()
    cal_far_peak = measure_peak(stream, duration=2.0)
    print(f"Peak à {FAR_CM} cm : {cal_far_peak:.5f}")

    if cal_near_peak <= cal_far_peak:
        print("\n⚠️  ATTENTION : le peak proche n'est pas plus fort que le peak loin.")
        print("   Vérifie que PC_emetteur.py tourne et que SEL est sur GND.")
    else:
        ratio = cal_near_peak / cal_far_peak
        print(f"\n✅ Calibration OK — ratio proche/loin = {ratio:.1f}x")

    # ── ÉTAPE 4 : Boucle de mesure ───────────────────────────────────────
    print("\n── MESURE EN COURS (Ctrl+C pour arrêter) ──\n")
    last_detect = 0.0

    while True:
        audio  = read_audio_block(stream)
        window = np.hanning(len(audio))
        fft    = np.fft.rfft(audio * window)
        freqs  = np.fft.rfftfreq(len(audio), 1 / SAMPLE_RATE)
        mag    = np.abs(fft)
        zone   = (freqs >= FFT_BAND_LOW) & (freqs <= FFT_BAND_HIGH)
        energy = float(np.max(mag[zone]))

        if energy <= fft_threshold:
            time.sleep(0.02)
            continue

        # Corrélation
        corr = np.abs(np.convolve(audio, template_rev, mode='valid'))
        if corr.size == 0:
            continue

        peak = float(np.max(corr))
        med  = float(np.median(corr))
        mad  = float(np.median(np.abs(corr - med)))
        corr_thr = med + 4 * mad * 1.4826

        now = time.time()
        if peak > corr_thr and (now - last_detect) > 0.15:
            dist = peak_to_distance(peak)
            bar  = int(np.clip((1 - (dist - NEAR_CM) / (FAR_CM - NEAR_CM)) * 20, 0, 20))
            bar_str = "█" * bar + "░" * (20 - bar)
            print(f"[{bar_str}] {dist:6.1f} cm  (peak={peak:.4f})")
            last_detect = now

        time.sleep(0.02)
