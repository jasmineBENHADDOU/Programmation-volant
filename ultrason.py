import sounddevice as sd
import numpy as np
import time

SAMPLE_RATE = 48000
BLOCKSIZE = 2048
DEVICE = 1

TARGET_MIN = 16000
TARGET_MAX = 19000
THRESHOLD = 5000000  # à ajuster après test

print("Écoute 20 kHz...")

with sd.InputStream(
    device=DEVICE,
    samplerate=SAMPLE_RATE,
    channels=2,
    dtype="float32",
    blocksize=BLOCKSIZE
) as stream:

    while True:
        audio, overflowed = stream.read(BLOCKSIZE)

        if overflowed:
            print("overflow")

        audio = audio[:, 0].astype(np.float32)

        window = np.hanning(len(audio))
        audio = audio * window

        fft = np.fft.rfft(audio)
        freqs = np.fft.rfftfreq(len(audio), 1 / SAMPLE_RATE)
        mag = np.abs(fft)

        zone = (freqs >= TARGET_MIN) & (freqs <= TARGET_MAX)
        energy = np.max(mag[zone])

        #print("energie 20kHz =", int(energy))

        if energy > THRESHOLD:
            print("ULTRASON 20 kHz DETECTE")

        #time.sleep(0.5)