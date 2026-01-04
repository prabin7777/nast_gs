"""Basic AM demodulator (envelope detector)."""
import numpy as np


def am_demod(iq: np.ndarray) -> np.ndarray:
    """Return baseband audio from IQ using simple envelope detection.

    Output is a float32 ndarray normalized to [-1, 1].
    """
    env = np.abs(iq)
    audio = env - np.mean(env)
    # simple normalization
    mx = np.max(np.abs(audio)) + 1e-12
    audio = audio / mx
    return audio.astype(np.float32)
