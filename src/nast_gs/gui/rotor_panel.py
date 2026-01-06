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

        # Default park position (requested)
        self._park_az = 100.0
        self._park_el = 90.0

        # Parking timer state
        self._park_timer = QtCore.QTimer(self)
        self._park_timer.setInterval(200)  # ms, 5 commands/sec
        self._park_timer.timeout.connect(self._park_tick)
        self._parking_active = False

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

        # Park button becomes a toggle: start/stop repeated park command
        self.park_btn = QtWidgets.QPushButton(f"Park Rotor (AZ={self._park_az:.0f} EL={self._park_el:.0f})")
        self.park_btn.setCheckable(True)
        self.park_btn.toggled.connect(self._on_park_toggled)

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

        # load saved config (safe if load_config() returns None)
        cfg = load_config() or {}
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
        if binary is not None:
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
            for pat in ("/dev/ttyUSB*",):
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
                cfg = load_config() or {}
                cfg["rotor_port"] = port
                cfg["rotor_baud"] = baud
                cfg["rotor_template"] = tmpl
                cfg["rotor_prosistel_binary"] = self.binary_chk.isChecked()
                save_config(cfg)

                self.connect_btn.setText("Disconnect")

                # Immediately start parking after connect (continuous)
                self._start_parking()

            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Rotor Connect", str(e))
                self.connect_btn.setChecked(False)

        else:
            self._stop_parking_ui()
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

    # ---------------- Parking logic ----------------

    def _on_park_toggled(self, checked: bool):
        if self._rotor is None:
            QtWidgets.QMessageBox.information(self, "Rotor", "Not connected")
            self.park_btn.setChecked(False)
            return

        if checked:
            self._start_parking()
        else:
            self._stop_parking_ui()

    def _start_parking(self):
        """Start repeatedly sending park command."""
        if self._rotor is None:
            return

        self._parking_active = True
        if not self.park_btn.isChecked():
            # keep UI in sync if called from connect()
            self.park_btn.setChecked(True)

        self.park_btn.setText(
            f"Parking... (AZ={self._park_az:.0f} EL={self._park_el:.0f}) Click to stop"
        )
        self._park_timer.start()
        self._park_tick()  # send immediately once

    def _stop_parking_ui(self):
        """Stop parking timer and reset button text."""
        self._parking_active = False
        try:
            self._park_timer.stop()
        except Exception:
            pass

        # reset button if it exists
        try:
            if self.park_btn.isChecked():
                self.park_btn.setChecked(False)
        except Exception:
            pass

        try:
            self.park_btn.setText(f"Park Rotor (AZ={self._park_az:.0f} EL={self._park_el:.0f})")
        except Exception:
            pass

    def _park_tick(self):
        """Send park command repeatedly. This solves 'moves 1-2 degrees then stops' behaviour."""
        if self._rotor is None:
            self._stop_parking_ui()
            return

        try:
            # Do NOT rely on rotor.park() because it may be a single command or unknown default.
            # Force the actual desired angles every tick.
            self._rotor.set_az_el(self._park_az, self._park_el)
        except Exception as e:
            self._stop_parking_ui()
            QtWidgets.QMessageBox.warning(self, "Rotor", str(e))
            return

    # ---------------- Helpers ----------------

    def has_rotor(self) -> bool:
        return self._rotor is not None

    def set_rotor_angle(self, az: float, el: float):
        """
        Called by tracking. If parking is active, ignore tracking commands
        to prevent fighting the park action.
        """
        if self._parking_active:
            return
        if self._rotor:
            self._rotor.set_az_el(az, el)
