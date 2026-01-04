import numpy as np
from nast_gs.demod.fm import fm_demod
from nast_gs.demod.cw import cw_demod


def test_fm_demod_basic():
    # synth a simple 1 kHz tone FM'd onto carrier
    fs = 48000
    t = np.arange(0, 0.01, 1 / fs)
    # baseband audio tone
    audio = np.sin(2 * np.pi * 1000 * t)
    # FM modulate on complex baseband with modest freq dev
    k = 2 * np.pi * 2000  # frequency sensitivity
    phase = np.cumsum(audio) * k / fs
    iq = np.exp(1j * phase)
    dem = fm_demod(iq)
    assert dem.shape[0] == iq.shape[0]
    assert abs(np.mean(dem)) < 1.0


def test_cw_demod_basic():
    fs = 48000
    t = np.arange(0, 0.01, 1 / fs)
    iq = np.exp(1j * 2 * np.pi * 1000 * t)
    env = cw_demod(iq)
    assert env.shape[0] == iq.shape[0]
    assert env.dtype.kind == 'f'
