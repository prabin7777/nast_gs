from PyQt6 import QtWidgets, QtCore
from typing import Optional
from datetime import datetime
from pathlib import Path

from nast_gs.gui.pass_panel import PassPanel


class TLEPanel(QtWidgets.QWidget):
    """
    Side panel to load/paste TLE and control propagation parameters.

    This panel is the SINGLE source of truth for:
      - TLE
      - Ground station location
      - Propagation window
      - Satellite nominal downlink frequency (Hz)
    """

    propagate_requested = QtCore.pyqtSignal(dict)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)


        # Force English digits inside this panel
        en_loc = QtCore.QLocale(QtCore.QLocale.Language.English, QtCore.QLocale.Country.UnitedStates)
        self.setLocale(en_loc)
        self.tle_text = QtWidgets.QPlainTextEdit()

        layout = QtWidgets.QFormLayout()

        # ---------- TLE ----------
        self.tle_text = QtWidgets.QPlainTextEdit()
        self.load_button = QtWidgets.QPushButton("Load TLE file…")
        self.load_button.clicked.connect(self._on_load_file)

        # ---------- Satellite downlink frequency (CRITICAL) ----------
        self.downlink_freq = QtWidgets.QDoubleSpinBox()
        self.downlink_freq.setRange(100e3, 6e9)
        self.downlink_freq.setDecimals(0)
        self.downlink_freq.setValue(145_800_000.0)
        self.downlink_freq.setSuffix(" Hz")
        self.downlink_freq.setToolTip(
            "Satellite nominal downlink frequency.\n"
            "This value is used as the Doppler reference."
        )

        # ---------- Ground station ----------
        self.gs_lat = QtWidgets.QDoubleSpinBox()
        self.gs_lat.setRange(-90.0, 90.0)
        self.gs_lat.setDecimals(6)
        self.gs_lat.setValue(25.0)

        self.gs_lon = QtWidgets.QDoubleSpinBox()
        self.gs_lon.setRange(-180.0, 180.0)
        self.gs_lon.setDecimals(6)
        self.gs_lon.setValue(-80.0)

        self.gs_alt = QtWidgets.QDoubleSpinBox()
        self.gs_alt.setRange(-500.0, 10000.0)
        self.gs_alt.setDecimals(1)
        self.gs_alt.setValue(5.0)
        self.gs_alt.setSuffix(" m")

        # ---------- Propagation window ----------
        self.minutes = QtWidgets.QSpinBox()
        self.minutes.setRange(1, 1440)
        self.minutes.setValue(90)

        self.step_s = QtWidgets.QSpinBox()
        self.step_s.setRange(1, 3600)
        self.step_s.setValue(60)

        self.propagate_btn = QtWidgets.QPushButton("Propagate")
        self.propagate_btn.clicked.connect(self._on_propagate)

        # ---------- Layout ----------
        layout.addRow(self.load_button)
        layout.addRow("TLE (name + 2 lines):", self.tle_text)

        layout.addRow("Downlink frequency:", self.downlink_freq)

        layout.addRow("GS Latitude (deg):", self.gs_lat)
        layout.addRow("GS Longitude (deg):", self.gs_lon)
        layout.addRow("GS Altitude:", self.gs_alt)

        layout.addRow("Minutes:", self.minutes)
        layout.addRow("Step (s):", self.step_s)

        layout.addRow(self.propagate_btn)

        # ---------- Pass prediction panel ----------
        self.pass_panel = PassPanel()
        layout.addRow(self.pass_panel)

        self.setLayout(layout)

    # ------------------------------------------------------------------

    def _on_load_file(self):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open TLE file",
            str(Path.cwd()),
            "TLE Files (*.tle *.txt);;All Files (*)",
        )
        if fn:
            with open(fn, "r", encoding="utf-8") as f:
                text = f.read().strip()
            self.tle_text.setPlainText(text)

    # ------------------------------------------------------------------

    def _on_propagate(self):
        text = self.tle_text.toPlainText().strip().splitlines()
        if len(text) < 3:
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid TLE",
                "Please provide a TLE with 3 lines:\n"
                "Satellite name\nLine 1\nLine 2",
            )
            return

        tle = [text[0].strip(), text[1].strip(), text[2].strip()]

        opts = {
            "tle": tle,
            "minutes": int(self.minutes.value()),
            "step_s": int(self.step_s.value()),
            "gs_lat": float(self.gs_lat.value()),
            "gs_lon": float(self.gs_lon.value()),
            "gs_alt": float(self.gs_alt.value()),
            "downlink_hz": float(self.downlink_freq.value()),
            "start": datetime.utcnow(),
        }

        # Update local pass panel context
        try:
            self.pass_panel.set_context(
                tle,
                opts["start"],
                opts["gs_lat"],
                opts["gs_lon"],
                opts["gs_alt"],
            )
        except Exception:
            pass

        # Emit to MainWindow / map / Doppler / SDR
        self.propagate_requested.emit(opts)
