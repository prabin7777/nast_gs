import numpy as np
import pyqtgraph as pg
from PyQt6 import QtWidgets


class SpectrumWidget(QtWidgets.QWidget):
    """
    GNU Radio-like spectrum:
    - Hann window
    - FFT shift
    - PSD in dB (10*log10(|X|^2))
    - DC removal
    - EMA averaging (stable trace)
    - fixed dB scale
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.plot = pg.PlotWidget()
        self.plot.setBackground("#1e1e1e")
        self.plot.showGrid(x=True, y=True, alpha=0.2)

        self.curve = self.plot.plot(pen=pg.mkPen((0, 255, 0), width=1))

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot)

        # Parameters similar to GNU Radio sinks
        self.nfft = 4096
        self.avg_alpha = 0.15

        # GNU Radio typical ranges
        self.db_min = -140.0
        self.db_max = -20.0

        self._avg_psd = None
        self._window = np.hanning(self.nfft).astype(np.float32)

        self.plot.setYRange(self.db_min, self.db_max)
        self.plot.setLabel("left", "Amplitude", units="dB")
        self.plot.setLabel("bottom", "Frequency", units="Hz")

    def _psd_db(self, iq: np.ndarray) -> np.ndarray | None:
        if iq is None or len(iq) < 64:
            return None

        x = np.asarray(iq, dtype=np.complex64)

        # pad or crop so we always compute PSD
        if len(x) < self.nfft:
            tmp = np.zeros(self.nfft, dtype=np.complex64)
            tmp[: len(x)] = x
            x = tmp
        else:
            x = x[: self.nfft]

        # DC removal (important for RTL)
        x = x - np.mean(x)

        # window
        x = x * self._window

        # FFT (shifted)
        X = np.fft.fftshift(np.fft.fft(x, self.nfft))

        # PSD in dB (power)
        p = (np.abs(X) ** 2).astype(np.float32)
        psd = 10.0 * np.log10(p + 1e-20).astype(np.float32)

        # reduce DC spike around center
        mid = self.nfft // 2
        psd[mid - 2 : mid + 2] = np.mean(psd)

        # EMA averaging
        if self._avg_psd is None:
            self._avg_psd = psd
        else:
            a = self.avg_alpha
            self._avg_psd = (a * psd + (1.0 - a) * self._avg_psd).astype(np.float32)

        return self._avg_psd

    def update_from_iq(self, iq: np.ndarray, center_hz: float, sample_rate: float):
        psd = self._psd_db(iq)
        if psd is None:
            return

        center_hz = float(center_hz)
        sample_rate = float(sample_rate)

        freqs = np.linspace(center_hz - sample_rate / 2.0,
                            center_hz + sample_rate / 2.0,
                            len(psd))

        self.curve.setData(freqs, psd)
