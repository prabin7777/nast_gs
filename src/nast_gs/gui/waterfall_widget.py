from PyQt6 import QtWidgets, QtGui, QtCore
import numpy as np
from collections import deque
from nast_gs.processing.spectrum import compute_spectrum


def _make_sdrsharp_lut() -> np.ndarray:
    # deep blue -> cyan -> yellow -> red
    lut = np.zeros(256, dtype=np.uint32)

    def clamp(v: float) -> int:
        if v < 0: return 0
        if v > 255: return 255
        return int(v)

    for i in range(256):
        t = i / 255.0
        if t < 0.35:
            k = t / 0.35
            r = 0
            g = clamp(220 * k)
            b = clamp(255 - 60 * k)
        elif t < 0.70:
            k = (t - 0.35) / 0.35
            r = clamp(255 * k)
            g = 255
            b = clamp(255 * (1.0 - k))
        elif t < 0.90:
            k = (t - 0.70) / 0.20
            r = 255
            g = clamp(255 * (1.0 - k))
            b = 0
        else:
            k = (t - 0.90) / 0.10
            r = 255
            g = clamp(80 * k)
            b = clamp(80 * k)

        lut[i] = (0xFF << 24) | (r << 16) | (g << 8) | b

    return lut


class _WaterfallImageView(QtWidgets.QWidget):
    def __init__(self, img: QtGui.QImage, parent=None):
        super().__init__(parent)
        self._img = img

    def paintEvent(self, event):
        qp = QtGui.QPainter(self)
        qp.drawImage(self.rect(), self._img)


class WaterfallWidget(QtWidgets.QWidget):
    """
    - Keeps last `history_seconds` of waterfall lines in RAM
    - Always stretches those lines to fill the whole widget height (no black after history)
    """
    def __init__(self, width: int = 900, height: int = 320, parent=None,
                 history_seconds: float = 10.0, update_dt_seconds: float = 0.2):
        super().__init__(parent)

        self.width_px = int(width)
        self.height_px = int(height)

        self.update_dt = float(update_dt_seconds)
        self.history_seconds = float(history_seconds)
        self.max_lines = max(1, int(round(self.history_seconds / self.update_dt)))

        self.nfft_default = 2048
        self.avg_alpha = 0.18

        # color scale control (your "gain")
        self.range_db = 90.0
        self.noise_margin_db = 15.0
        self.level_offset_db = 0.0

        self._noise_floor_db = None
        self._cal_count = 0
        self._cal_target = 25

        self._lut = _make_sdrsharp_lut()
        self._avg_psd = None

        self._lines = deque(maxlen=self.max_lines)  # each line is uint8[width_px]

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        left = QtWidgets.QVBoxLayout()
        left.setContentsMargins(6, 6, 0, 6)

        self.level_label = QtWidgets.QLabel("Calibrating...")
        self.level_label.setStyleSheet("color:#cfcfcf; font-size:11px;")
        self.level_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.level_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Vertical)
        self.level_slider.setMinimum(-80)
        self.level_slider.setMaximum(80)
        self.level_slider.setValue(0)
        self.level_slider.setTickPosition(QtWidgets.QSlider.TickPosition.TicksBothSides)
        self.level_slider.setTickInterval(10)
        self.level_slider.valueChanged.connect(self._on_level_changed)

        left.addWidget(self.level_label)
        left.addWidget(self.level_slider, 1)
        root.addLayout(left)

        self.img = QtGui.QImage(self.width_px, self.height_px, QtGui.QImage.Format.Format_ARGB32)
        self.img.fill(QtGui.QColor(0, 0, 0))

        self.image_widget = _WaterfallImageView(self.img)
        self.image_widget.setMinimumSize(self.width_px, self.height_px)
        root.addWidget(self.image_widget, 1)

        self.setLayout(root)

    def _on_level_changed(self, v: int):
        self.level_offset_db = float(v)
        self._update_label()

    def _update_label(self):
        if self._noise_floor_db is None:
            self.level_label.setText("Calibrating...")
            return
        db_min = (self._noise_floor_db - self.noise_margin_db) + self.level_offset_db
        db_max = db_min + self.range_db
        self.level_label.setText(f"{db_min:.0f} .. {db_max:.0f} dB")

    def clear(self):
        self._avg_psd = None
        self._noise_floor_db = None
        self._cal_count = 0
        self.level_slider.setValue(0)
        self.level_offset_db = 0.0
        self._lines.clear()
        self.img.fill(QtGui.QColor(0, 0, 0))
        self._update_label()
        self.image_widget.update()

    def _estimate_noise_floor(self, psd_db: np.ndarray) -> float:
        return float(np.percentile(psd_db, 20))

    def _render_from_memory_scaled(self):
        self.img.fill(QtGui.QColor(0, 0, 0))
        if not self._lines:
            self.image_widget.update()
            return

        # newest at top
        rows = list(self._lines)
        rows = rows[::-1]

        # stretch last N rows to full height
        src_h = len(rows)
        if src_h <= 1:
            idx_map = np.zeros(self.height_px, dtype=np.int32)
        else:
            idx_map = np.linspace(0, src_h - 1, self.height_px).astype(np.int32)

        painter = QtGui.QPainter(self.img)
        for y in range(self.height_px):
            pix = rows[idx_map[y]]
            line_argb = self._lut[pix]
            line_bytes = line_argb.tobytes()
            line_img = QtGui.QImage(
                line_bytes,
                self.width_px,
                1,
                self.width_px * 4,
                QtGui.QImage.Format.Format_ARGB32,
            )
            painter.drawImage(0, y, line_img)
        painter.end()
        self.image_widget.update()

    def update_from_iq(self, iq, nfft: int | None = None):
        nfft = int(nfft or self.nfft_default)

        _, psd_db = compute_spectrum(iq, nfft=nfft)
        psd_db = psd_db.astype(np.float32)

        # averaging
        if self._avg_psd is None or len(self._avg_psd) != len(psd_db):
            self._avg_psd = psd_db
        else:
            a = float(self.avg_alpha)
            self._avg_psd = (a * psd_db + (1.0 - a) * self._avg_psd).astype(np.float32)

        row_db = self._avg_psd

        # noise floor calibration
        nf = self._estimate_noise_floor(row_db)
        if self._noise_floor_db is None:
            self._noise_floor_db = nf
            self._cal_count = 1
        elif self._cal_count < self._cal_target:
            self._noise_floor_db = 0.85 * self._noise_floor_db + 0.15 * nf
            self._cal_count += 1

        self._update_label()

        # resample to width
        if len(row_db) != self.width_px:
            idx = np.linspace(0, len(row_db) - 1, self.width_px).astype(np.int32)
            row_db = row_db[idx]

        db_min = (self._noise_floor_db - self.noise_margin_db) + self.level_offset_db
        db_max = db_min + self.range_db

        row_db = np.clip(row_db, db_min, db_max)
        norm = (row_db - db_min) / (db_max - db_min + 1e-9)
        pix = (norm * 255.0).astype(np.uint8)

        self._lines.append(pix)
        self._render_from_memory_scaled()
