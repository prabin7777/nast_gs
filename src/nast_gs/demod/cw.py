"""Simple CW (continuous wave) demodulator utilities."""
import numpy as np


def cw_demod(iq: np.ndarray) -> np.ndarray:
    """Return envelope (amplitude) detector of IQ samples for CW tone audio output."""
    mag = np.abs(iq)
    # simple DC removal
    mag = mag - np.mean(mag)
    return mag
