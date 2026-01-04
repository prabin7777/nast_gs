from PyQt6 import QtWidgets, QtCore
from typing import Optional
from datetime import datetime
from pathlib import Path
from nast_gs.gui.pass_panel import PassPanel


class TLEPanel(QtWidgets.QWidget):
    """Side panel to load/paste TLE and control propagation parameters."""

    propagate_requested = QtCore.pyqtSignal(dict)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        layout = QtWidgets.QFormLayout()

        self.tle_text = QtWidgets.QPlainTextEdit()
        self.load_button = QtWidgets.QPushButton("Load TLE file...")
        self.load_button.clicked.connect(self._on_load_file)

        # Propagation parameters
        self.gs_lat = QtWidgets.QDoubleSpinBox()
        self.gs_lat.setRange(-90, 90)
        self.gs_lat.setValue(25.0)

        self.gs_lon = QtWidgets.QDoubleSpinBox()
        self.gs_lon.setRange(-180, 180)
        self.gs_lon.setValue(-80.0)

        # altitude (meters)
        self.gs_alt = QtWidgets.QDoubleSpinBox()
        self.gs_alt.setRange(-500.0, 10000.0)
        self.gs_alt.setValue(5.0)
        self.gs_alt.setSuffix(" m")

        self.minutes = QtWidgets.QSpinBox()
        self.minutes.setRange(1, 1440)
        self.minutes.setValue(90)

        self.step_s = QtWidgets.QSpinBox()
        self.step_s.setRange(1, 3600)
        self.step_s.setValue(60)

        self.propagate_btn = QtWidgets.QPushButton("Propagate")
        self.propagate_btn.clicked.connect(self._on_propagate)

        layout.addRow(self.load_button, None)
        layout.addRow("TLE (name + 2 lines):", self.tle_text)
        layout.addRow("GS Latitude (deg):", self.gs_lat)
        layout.addRow("GS Longitude (deg):", self.gs_lon)
        layout.addRow("GS Altitude (m):", self.gs_alt)
        layout.addRow("Minutes:", self.minutes)
        layout.addRow("Step (s):", self.step_s)
        layout.addRow(self.propagate_btn)

        # Pass prediction UI below propagation controls for easier access
        self.pass_panel = PassPanel()
        layout.addRow(self.pass_panel)

        self.setLayout(layout)

    def _on_load_file(self):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open TLE file", str(Path.cwd()), "TLE Files (*.tle *.txt);;All Files (*)")
        if fn:
            with open(fn, "r") as f:
                text = f.read().strip()
            self.tle_text.setPlainText(text)

    def _on_propagate(self):
        text = self.tle_text.toPlainText().strip().splitlines()
        if len(text) < 3:
            QtWidgets.QMessageBox.warning(self, "Invalid TLE", "Please provide a TLE with 3 lines: name, line1, line2")
            return
        tle = [text[0].strip(), text[1].strip(), text[2].strip()]
        opts = {
            "tle": tle,
            "minutes": int(self.minutes.value()),
            "step_s": int(self.step_s.value()),
            "gs_lat": float(self.gs_lat.value()),
            "gs_lon": float(self.gs_lon.value()),
            "gs_alt": float(self.gs_alt.value()),
            "start": datetime.utcnow(),
        }
        # update local pass panel context and emit propagate event for map/other UI
        try:
            self.pass_panel.set_context(tle, opts["start"], opts["gs_lat"], opts["gs_lon"], opts.get("gs_alt", 0.0))
        except Exception:
            pass
        self.propagate_requested.emit(opts)
