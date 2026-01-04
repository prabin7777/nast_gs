import numpy as np


def compute_spectrum(iq: np.ndarray, nfft: int = 1024):
    """
    GNU Radio-like spectrum computation:
    - DC removal
    - Hann window
    - FFT shift
    - PSD in dB: 10*log10(|X|^2)
    Returns:
        bins: normalized frequency bins from -0.5..+0.5 (like GNURadio baseband)
        psd_db: PSD in dB (float32)
    """
    if iq is None or len(iq) < 16:
        bins = np.linspace(-0.5, 0.5, nfft, endpoint=False)
        return bins, np.full(nfft, -200.0, dtype=np.float32)

    x = np.asarray(iq, dtype=np.complex64)

    # pad/crop to nfft
    if len(x) < nfft:
        tmp = np.zeros(nfft, dtype=np.complex64)
        tmp[: len(x)] = x
        x = tmp
    else:
        x = x[:nfft]

    # DC remove (RTL-SDR center spike reduction)
    x = x - np.mean(x)

    # Hann window (same default as GNU Radio sinks)
    w = np.hanning(nfft).astype(np.float32)
    x = x * w

    # FFT shift
    X = np.fft.fftshift(np.fft.fft(x, nfft))

    # PSD power in dB (GNU Radio style)
    p = (np.abs(X) ** 2).astype(np.float32)
    psd_db = (10.0 * np.log10(p + 1e-20)).astype(np.float32)

    # bins are normalized baseband bins
    bins = np.linspace(-0.5, 0.5, nfft, endpoint=False)

    # soften the remaining DC bin area
    mid = nfft // 2
    psd_db[mid - 2: mid + 2] = np.mean(psd_db)

    return bins, psd_db
