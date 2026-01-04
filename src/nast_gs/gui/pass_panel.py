from PyQt6 import QtWidgets, QtCore
from nast_gs.prop.propagator import compute_passes


class PassPanel(QtWidgets.QWidget):
    """Shows upcoming satellite passes for the selected TLE and ground station."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        hl = QtWidgets.QHBoxLayout()
        self.hours_spin = QtWidgets.QSpinBox()
        self.hours_spin.setRange(1, 168)
        self.hours_spin.setValue(48)
        hl.addWidget(QtWidgets.QLabel("Lookahead (hours):"))
        hl.addWidget(self.hours_spin)
        self.compute_btn = QtWidgets.QPushButton("Compute Passes")
        self.compute_btn.clicked.connect(self._on_compute)
        hl.addWidget(self.compute_btn)
        layout.addLayout(hl)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["AOS", "LOS", "TCA", "Max EL (°)", "Duration (s)"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self._last_args = None

    def _on_compute(self):
        if self._last_args is None:
            QtWidgets.QMessageBox.information(self, "No TLE", "Please propagate a TLE first to compute passes")
            return
        tle, start, gs_lat, gs_lon, gs_alt = self._last_args
        self.compute_and_update(tle, start, hours=self.hours_spin.value(), gs_lat=gs_lat, gs_lon=gs_lon, gs_alt_m=gs_alt)

    def compute_and_update(self, tle, start, hours: int, gs_lat: float, gs_lon: float, gs_alt_m: float = 0.0):
        passes = compute_passes(tle, start, hours=hours, gs_lat=gs_lat, gs_lon=gs_lon, gs_alt_m=gs_alt_m)
        self.update_passes(passes)

    def update_passes(self, passes):
        self.table.setRowCount(0)
        for p in passes:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(p['aos'].isoformat()))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(p['los'].isoformat()))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(p['tca'].isoformat()))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(f"{p['max_el_deg']:.2f}"))
            self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(str(p['duration_s'])))

    def set_context(self, tle, start, gs_lat, gs_lon, gs_alt_m=0.0):
        self._last_args = (tle, start, gs_lat, gs_lon, gs_alt_m)
        # compute automatically with current hours
        self.compute_and_update(tle, start, hours=self.hours_spin.value(), gs_lat=gs_lat, gs_lon=gs_lon, gs_alt_m=gs_alt_m)
