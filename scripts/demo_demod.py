"""Generate a synthetic FM signal, demodulate (FM) and write audio to a WAV file."""
import numpy as np
from scipy.io import wavfile
from nast_gs.demod.fm import fm_demod


def synth_fm(duration_s=2.0, fs=48000, tone_hz=1000, freq_dev=2000.0):
    t = np.arange(0, duration_s, 1 / fs)
    audio = 0.5 * np.sin(2 * np.pi * tone_hz * t)
    phase = np.cumsum(audio) * (2 * np.pi * freq_dev) / fs
    iq = np.exp(1j * phase)
    return iq, fs


def main():
    iq, fs = synth_fm()
    audio = fm_demod(iq)
    # normalize and convert to int16
    audio = audio / (np.max(np.abs(audio)) + 1e-12)
    audio16 = (audio * 0.9 * 32767).astype(np.int16)
    wavfile.write("demo_out.wav", fs, audio16)
    print("Wrote demo_out.wav")


if __name__ == "__main__":
    main()
