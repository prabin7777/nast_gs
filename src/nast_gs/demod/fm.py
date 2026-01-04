import numpy as np
from scipy.signal import firwin, lfilter, decimate, resample_poly


def fm_demod_to_audio(
    iq: np.ndarray,
    fs_in: float,
    fs_audio: int = 48000,
    deviation: float = 75_000.0,
    deemph_tau: float = 75e-6,   # 75 µs (US), use 50e-6 for EU
):
    """
    Proper Wideband FM (Broadcast FM) demodulation
    Equivalent to SDR# / GNU Radio WBFM
    """

    iq = iq.astype(np.complex64, copy=False)

    # -------------------------------------------------
    # 1) RF channel filter (~200 kHz)
    # -------------------------------------------------
    rf_bw = 200_000.0
    rf_taps = firwin(129, rf_bw, fs=fs_in)
    iq = lfilter(rf_taps, 1.0, iq)

    # -------------------------------------------------
    # 2) Decimate to ~240 ksps
    # -------------------------------------------------
    decim = int(fs_in // 240_000)
    if decim < 1:
        decim = 1

    iq = decimate(iq, decim, ftype="fir", zero_phase=False)
    fs_if = fs_in / decim

    # -------------------------------------------------
    # 3) FM discriminator (quadrature)
    # -------------------------------------------------
    x = iq[1:] * np.conj(iq[:-1])
    fm = np.angle(x)
    fm = np.concatenate([fm, [0.0]]).astype(np.float32)

    # normalize by deviation
    fm *= fs_if / (2.0 * np.pi * deviation)

    # -------------------------------------------------
    # 4) Audio LPF (~15 kHz)
    # -------------------------------------------------
    af_taps = firwin(101, 15_000, fs=fs_if)
    fm = lfilter(af_taps, 1.0, fm)

    # -------------------------------------------------
    # 5) De-emphasis
    # -------------------------------------------------
    alpha = np.exp(-1.0 / (fs_if * deemph_tau))
    y = np.empty_like(fm)
    z = 0.0
    for i, v in enumerate(fm):
        z = alpha * z + (1.0 - alpha) * v
        y[i] = z
    fm = y

    # -------------------------------------------------
    # 6) Resample to audio rate (48 kHz)
    # -------------------------------------------------
    audio = resample_poly(fm, fs_audio, int(fs_if))

    # -------------------------------------------------
    # 7) Normalize
    # -------------------------------------------------
    audio -= np.mean(audio)
    peak = np.max(np.abs(audio)) + 1e-12
    audio = audio / peak * 0.8

    return audio.astype(np.float32)