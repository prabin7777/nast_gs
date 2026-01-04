from PyQt6 import QtWidgets
import numpy as np

try:
    import pyqtgraph as pg
except Exception:
    pg = None

from nast_gs.gui.waterfall_widget import WaterfallWidget


def _psd_db(iq: np.ndarray, nfft: int) -> np.ndarray:
    """Return PSD in dB (float32) for complex IQ."""
    iq = np.asarray(iq)
    if iq.size < nfft:
        # pad if needed
        pad = np.zeros(nfft - iq.size, dtype=iq.dtype)
        x = np.concatenate([iq, pad])
    else:
        x = iq[:nfft]

    # window
    w = np.hanning(nfft).astype(np.float32)
    x = x.astype(np.complex64) * w

    # FFT
    X = np.fft.fftshift(np.fft.fft(x, nfft))
    p = (np.abs(X) ** 2).astype(np.float32)

    # log
    p_db = 10.0 * np.log10(p + 1e-12)
    return p_db


class SpectrumWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Spectrum & Waterfall")

        self.update_dt = 0.2
        self.nfft = 4096  # higher = smoother line

        self._manual_y = False
        self._internal_range_set = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        if pg is None:
            self.plot = None
            layout.addWidget(QtWidgets.QLabel("pyqtgraph not available"))
        else:
            self.plot = pg.PlotWidget()
            self.plot.setBackground((30, 30, 30))
            self.plot.showGrid(x=True, y=True, alpha=0.25)

            self.plot.setLabel("left", "Amplitude", units="dB")
            self.plot.setLabel("bottom", "Frequency", units="MHz")

            # X locked, Y zoomable
            self.plot.setMouseEnabled(x=False, y=True)
            self.plot.enableAutoRange(x=False, y=True)

            self.curve = self.plot.plot([], [], pen=pg.mkPen((0, 255, 0), width=1))
            layout.addWidget(self.plot, 2)

            vb = self.plot.getViewBox()
            vb.sigRangeChanged.connect(self._on_range_changed)

        # Waterfall: keep 10s memory but stretched to fill height (your updated widget does this)
        self.waterfall = WaterfallWidget(
            width=1100,
            height=320,
            history_seconds=10.0,
            update_dt_seconds=self.update_dt
        )
        layout.addWidget(self.waterfall, 3)

        self.setLayout(layout)
        self.resize(1200, 760)

    def _on_range_changed(self, *args):
        if self._internal_range_set:
            return
        self._manual_y = True

    def update_from_iq(self, iq, center_hz: float, sample_rate: float):
        # Waterfall always updates
        self.waterfall.update_from_iq(iq, nfft=self.nfft)

        if self.plot is None:
            return

        cf = float(center_hz)
        sr = float(sample_rate)

        # PSD in dB (we do it ourselves so x-axis is never 0..1 MHz)
        p_db = _psd_db(iq, self.nfft)

        # Frequency axis locked to SDR center +/- Fs/2
        f0 = cf - sr / 2.0
        f1 = cf + sr / 2.0
        x_hz = np.linspace(f0, f1, len(p_db), endpoint=False)
        x_mhz = x_hz / 1e6

        self.curve.setData(x_mhz, p_db)

        # lock X every update
        self._internal_range_set = True
        try:
            self.plot.setXRange(f0 / 1e6, f1 / 1e6, padding=0.0)
        finally:
            self._internal_range_set = False

        # auto Y until user touches Y
        if not self._manual_y:
            y_lo = float(np.percentile(p_db, 5))
            y_hi = float(np.percentile(p_db, 99.5))
            if (y_hi - y_lo) < 10:
                y_hi = y_lo + 10
            self._internal_range_set = True
            try:
                self.plot.setYRange(y_lo - 5.0, y_hi + 5.0, padding=0.0)
            finally:
                self._internal_range_set = False
