from PyQt6 import QtWidgets, QtCore
from typing import Optional
import inspect

from nast_gs.rotor.serial import SerialRotor, ProsistelRotor
from nast_gs.config import load_config, save_config


class RotorPanel(QtWidgets.QWidget):
    """UI to manage rotor serial connection and prosistel/generic commands."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        layout = QtWidgets.QFormLayout()

        self.port_combo = QtWidgets.QComboBox()
        self.refresh_btn = QtWidgets.QPushButton("Refresh Ports")
        self.refresh_btn.clicked.connect(self._refresh_ports)

        self.baud_combo = QtWidgets.QComboBox()
        self.baud_combo.addItems(["4800", "9600", "19200", "38400", "57600", "115200"])

        self.protocol_combo = QtWidgets.QComboBox()
        self.protocol_combo.addItems(["Prosistel", "Generic"])

        self.cmd_template = QtWidgets.QLineEdit()
        self.cmd_template.setText("P AZ{az:03.0f} EL{el:03.0f}\r")

        self.binary_chk = QtWidgets.QCheckBox("Use Prosistel binary packet (16-byte)")

        self.connect_btn = QtWidgets.QPushButton("Connect")
        self.connect_btn.setCheckable(True)
        self.connect_btn.toggled.connect(self._on_toggle_connect)

        self.test_move_btn = QtWidgets.QPushButton("Test Move (AZ=180 EL=45)")
        self.test_move_btn.clicked.connect(self._on_test_move)

        self.park_btn = QtWidgets.QPushButton("Park Rotor (AZ=100 EL=90)")
        self.park_btn.clicked.connect(self._on_park)

        layout.addRow(self.port_combo, self.refresh_btn)
        layout.addRow("Baud:", self.baud_combo)
        layout.addRow("Protocol:", self.protocol_combo)
        layout.addRow("Cmd template:", self.cmd_template)
        layout.addRow(self.binary_chk)
        layout.addRow(self.connect_btn)
        layout.addRow(self.test_move_btn)
        layout.addRow(self.park_btn)

        self.setLayout(layout)

        self._rotor = None
        self._refresh_ports()

        # load saved config
        cfg = load_config()
        port = cfg.get("rotor_port")
        baud = cfg.get("rotor_baud")
        tmpl = cfg.get("rotor_template")

        if port:
            idx = self.port_combo.findText(port)
            if idx >= 0:
                self.port_combo.setCurrentIndex(idx)

        if baud:
            idx = self.baud_combo.findText(str(baud))
            if idx >= 0:
                self.baud_combo.setCurrentIndex(idx)

        if tmpl:
            self.cmd_template.setText(tmpl)

        binary = cfg.get("rotor_prosistel_binary")
        if binary:
            self.binary_chk.setChecked(bool(binary))

    def _refresh_ports(self):
        current = self.port_combo.currentText()
        self.port_combo.clear()

        ports_found = []
        try:
            import serial.tools.list_ports as list_ports
            for p in list_ports.comports():
                ports_found.append(p.device)
        except Exception:
            import glob
            for pat in ("/dev/ttyUSB*", "/dev/ttyACM*", "/dev/ttyS*"):
                ports_found.extend(glob.glob(pat))

        if ports_found:
            for d in ports_found:
                self.port_combo.addItem(d)
            if current:
                idx = self.port_combo.findText(current)
                if idx >= 0:
                    self.port_combo.setCurrentIndex(idx)
        else:
            self.port_combo.addItem("No ports found")
            self.port_combo.setCurrentIndex(0)

    def _make_prosistel_rotor(self, port: str, baud: int, tmpl: str, binary: bool):
        """
        Build ProsistelRotor but only pass kwargs it actually supports.
        This avoids crashes when ProsistelRotor signature differs across versions.
        """
        sig = inspect.signature(ProsistelRotor.__init__)
        supported = set(sig.parameters.keys())

        kwargs = {"port": port, "baud": baud}

        # Only pass if ProsistelRotor supports them
        if "template" in supported:
            kwargs["template"] = tmpl
        if "binary" in supported:
            kwargs["binary"] = binary

        return ProsistelRotor(**kwargs)

    def _on_toggle_connect(self, checked: bool):
        if checked:
            port = self.port_combo.currentText()
            if not port or "No ports" in port:
                QtWidgets.QMessageBox.information(self, "Rotor", "No serial port selected or no ports found.")
                self.connect_btn.setChecked(False)
                return

            baud = int(self.baud_combo.currentText())
            tmpl = self.cmd_template.text().strip()
            proto = self.protocol_combo.currentText()

            try:
                if proto == "Prosistel":
                    rotor = self._make_prosistel_rotor(
                        port=port,
                        baud=baud,
                        tmpl=tmpl,
                        binary=self.binary_chk.isChecked(),
                    )
                else:
                    rotor = SerialRotor(port, baud=baud, template=tmpl)

                rotor.connect()
                self._rotor = rotor

                # persist
                cfg = load_config()
                cfg["rotor_port"] = port
                cfg["rotor_baud"] = baud
                cfg["rotor_template"] = tmpl
                cfg["rotor_prosistel_binary"] = self.binary_chk.isChecked()
                save_config(cfg)

                self.connect_btn.setText("Disconnect")

            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Rotor Connect", str(e))
                self.connect_btn.setChecked(False)

        else:
            try:
                if self._rotor:
                    self._rotor.disconnect()
            finally:
                self._rotor = None
                self.connect_btn.setText("Connect")

    def _on_test_move(self):
        if self._rotor is None:
            QtWidgets.QMessageBox.information(self, "Rotor", "Not connected")
            return
        try:
            self._rotor.set_az_el(180.0, 45.0)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Rotor", str(e))

    def _on_park(self):
        if self._rotor is None:
            QtWidgets.QMessageBox.information(self, "Rotor", "Not connected")
            return
        try:
            self._rotor.park()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Rotor", str(e))

    def has_rotor(self) -> bool:
        return self._rotor is not None

    def set_rotor_angle(self, az: float, el: float):
        if self._rotor:
            self._rotor.set_az_el(az, el)
