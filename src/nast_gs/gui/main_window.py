from PyQt6 import QtWidgets, QtCore, QtGui
from pathlib import Path
import sys

from nast_gs.sdr.gqrx_launcher import ensure_gqrx_running

from .map_view import MapWindow
from .tle_panel import TLEPanel

from nast_gs.prop.propagator import propagate_tle
from nast_gs.sdr.device import SimulatedSDR
from nast_gs.sdr.doppler import DopplerController
from nast_gs.rotor.controller import SimulatedRotor
from nast_gs.config import load_config, save_config
from nast_gs.ntp import get_ntp_time


def _asset_path(filename: str) -> str:
    """
    Works for:
      - running from source tree: src/nast_gs/gui/main_window.py
      - PyInstaller bundle: add-data "src/nast_gs/assets" -> "nast_gs/assets"
    """
    if hasattr(sys, "_MEIPASS"):
        return str(Path(sys._MEIPASS) / "nast_gs" / "assets" / filename)

    # main_window.py is in src/nast_gs/gui/, assets are in src/nast_gs/assets/
    return str(Path(__file__).resolve().parents[1] / "assets" / filename)

class AboutDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About App")
        self.setModal(True)
        self.resize(900, 650)   # better than min sizes for long manual

        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("NAST Ground Station Software")
        f = title.font()
        f.setPointSize(12)
        f.setBold(True)
        title.setFont(f)

        info = QtWidgets.QTextBrowser()
        info.setOpenExternalLinks(True)
        info.setReadOnly(True)

        developer = "Er. Damodar Pokhrel"
        project = "Space Research Centre, Nepal Academy of Science and Technology (NAST) Ground Station"
        dev_email = "prabinpokharel7777@gmail.com"
        supervisor_name = "Er. Hari Ram Shrestha"
        supervisor_email = "haristha9@gmail.com"
        github = "https://github.com/prabin7777/nast_gs"

        gqrx_link = "https://github.com/gqrx-sdr/gqrx/releases/tag/v2.14.5"
        zadig_link = "https://zadig.akeo.ie/"

        manual_html = f"""
        <h3>User Manual (Quick Setup)</h3>

        <p><b>Downloads</b></p>
        <ul>
          <li><b>Gqrx:</b> <a href="{gqrx_link}">{gqrx_link}</a></li>
          <li><b>Zadig (Windows RTL-SDR driver):</b> <a href="{zadig_link}">{zadig_link}</a></li>
        </ul>

        <ol>
          <li><b>Install Gqrx</b><br>
              Download and install <b>Gqrx</b> from the link above.</li>

          <li><b>Install RTL-SDR Driver (Windows only)</b><br>
              If RTL-SDR is not detected, use <b>Zadig</b> to install the WinUSB driver for the correct device.</li>

          <li><b>Enable TCP Control in Gqrx</b><br>
              Open Gqrx and enable <b>Remote control / TCP</b>. Set host/port and keep it running.</li>

          <li><b>Load TLE Data</b><br>
              Click <b>Load TLE file</b> and import the satellite TLE (name + 2 lines).</li>

          <li><b>Set Frequency</b><br>
              Enter the satellite <b>downlink frequency</b>. This is used as the Doppler reference.</li>

          <li><b>Set Ground Station Location</b><br>
              Enter accurate <b>GS latitude</b>, <b>longitude</b>, and <b>altitude</b>.</li>

          <li><b>Propagate</b><br>
              Click <b>Propagate</b> to plot the track and compute pass prediction.</li>

          <li><b>SDR Panel Setup</b><br>
              Press <b>Refresh Devices</b>. Select <b>Gqrx External</b> and set <b>Gqrx host</b> and <b>port</b>
              to match Gqrx TCP settings.</li>

          <li><b>Start Doppler Updates</b><br>
              Click <b>Start Doppler Updates</b>.</li>

          <li><b>Start Device</b><br>
              Click <b>Start Device</b>. The tuned frequency in Gqrx will update via TCP.</li>

          <li><b>Start Tracking</b><br>
              Click <b>Start Tracking</b>. Watch live <b>AZ/EL/Range/Range-rate</b>.</li>

          <li><b>Enable Rotor</b><br>
              Click <b>Enable Rotor</b> to send azimuth/elevation to the antenna positioner.</li>

          <li><b>Rotor Connection</b><br>
              Click <b>Refresh Ports</b>, select correct port (commonly <b>/dev/ttyUSB0</b>), set <b>9600</b> baud,
              choose <b>Prosistel</b>, tick <b>16-byte</b> if required, then press <b>Connect</b>.</li>

          <li><b>Signal Visualization and Recording</b><br>
              Use the Gqrx window for spectrum/waterfall view, reception tuning, and recording.</li>

          <li><b>Parking the Rotor (AZ=100, EL=90)</b><br>
              If the rotor does not park correctly, press <b>Park Rotor</b> and wait until it reaches the park position.</li>
        </ol>
        """

        info.setHtml(
            f"""
            <style>
              body {{ font-family: Arial; font-size: 12px; }}
              h3 {{ margin-top: 14px; }}
              li {{ margin-bottom: 8px; }}
              hr {{ margin: 14px 0; }}
            </style>

            <p><b>Project:</b><br>{project}</p>
            <p><b>Developer:</b><br>{developer}<br>
               <b>Email:</b> {dev_email}</p>
            <p><b>Supervisor:</b><br>{supervisor_name}<br>
               <b>Email:</b> {supervisor_email}</p>
            <p><b>GitHub:</b><br>
               <a href="{github}">{github}</a></p>
            <hr>
            {manual_html}
            """
        )

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        btns.accepted.connect(self.accept)

        layout.addWidget(title)
        layout.addWidget(info, 1)
        layout.addWidget(btns)


class MainWindow(QtWidgets.QMainWindow):
    """
    One-frequency design:
      - User inputs TLE + satellite downlink frequency in TLE panel.
      - That downlink frequency is the ONLY nominal frequency.
      - DopplerController always references that nominal downlink.
      - Tuned (corrected) frequency is pushed to SDRPanel.apply_doppler(),
        which will command Gqrx (TCP) or RTL/Soapy (direct) depending on selection.
    """

    def __init__(self):
        super().__init__()

        self._rotor_is_parked = False

        # Park position
        self._park_az = 100.0
        self._park_el = 90.0

        self.setWindowTitle("NAST_GS_DP_TRACKER_V1")
        self.resize(1400, 900)

        # Window icon (title bar + taskbar)
        try:
            self.setWindowIcon(QtGui.QIcon(_asset_path("NAST_GS_TRACKER_1.png")))
        except Exception:
            pass

        central = QtWidgets.QWidget()
        central_layout = QtWidgets.QVBoxLayout(central)
        central_layout.setContentsMargins(2, 2, 2, 2)
        central_layout.setSpacing(4)

        # ----- Header bar with logos + title + About button (RIGHT) -----
        header = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(6, 6, 6, 2)
        header_layout.setSpacing(10)

        header.setFixedHeight(58)
        header.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed
        )

        self.nast_logo_lbl = QtWidgets.QLabel()
        self.nepal_flag_lbl = QtWidgets.QLabel()

        self.nast_logo_lbl.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self.nepal_flag_lbl.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)

        title_lbl = QtWidgets.QLabel("Space Research Centre, Nepal Academy of Science and Technology (NAST)")
        title_font = title_lbl.font()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title_lbl.setFont(title_font)

        self._load_header_images()

        self.about_btn = QtWidgets.QPushButton("Press for Operator Help")
        self.about_btn.clicked.connect(self._open_about)
        self.about_btn.setFixedHeight(34)
        self.about_btn.setMinimumWidth(110)

        header_layout.addWidget(self.nast_logo_lbl, 0)
        header_layout.addWidget(self.nepal_flag_lbl, 0)
        header_layout.addWidget(title_lbl, 1)
        header_layout.addWidget(self.about_btn, 0)

        central_layout.addWidget(header, 0)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        # left: TLE panel (scrollable)
        self.tle_panel = TLEPanel()
        left_scroll = QtWidgets.QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setWidget(self.tle_panel)
        left_scroll.setMinimumWidth(220)
        self.tle_panel.setMinimumWidth(220)
        splitter.addWidget(left_scroll)

        # center: map
        self.map = MapWindow()
        try:
            self.map.view.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Expanding,
            )
        except Exception:
            pass

        center_container = QtWidgets.QWidget()
        center_layout = QtWidgets.QVBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.addWidget(self.map.view, 1)
        try:
            self.map.view.setMinimumSize(600, 360)
        except Exception:
            pass
        splitter.addWidget(center_container)

        # right: controls (scrollable)
        controls_widget = QtWidgets.QWidget()
        controls_layout = QtWidgets.QVBoxLayout(controls_widget)
        controls_layout.setContentsMargins(6, 6, 6, 6)

        controls_widget.setMinimumWidth(320)
        controls_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        right_scroll = QtWidgets.QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setWidget(controls_widget)
        splitter.addWidget(right_scroll)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 0)
        try:
            splitter.setSizes([200, 880, 320])
        except Exception:
            pass

        central_layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

        # --- Signals ---
        self.tle_panel.propagate_requested.connect(self.on_propagate)

        # --- Runtime state ---
        self._doppler_enabled = False
        self._current_tle = None
        self._current_gs = (25.0, -80.0)
        self._downlink_hz = 145_800_000.0
        self._ntp_time = None

        # --- SDR and Doppler ---
        self.sdr = SimulatedSDR()
        self.doppler_ctrl = DopplerController(self.sdr, center_freq_hz=self._downlink_hz)

        # --- Right controls UI ---
        sd_widget = QtWidgets.QWidget()
        sd_layout = QtWidgets.QVBoxLayout(sd_widget)

        self.sdr_freq_label = QtWidgets.QLabel(f"SDR tuned: {self._downlink_hz/1e6:.6f} MHz")

        self.start_doppler_btn = QtWidgets.QPushButton("Start Doppler Updates")
        self.start_doppler_btn.setCheckable(True)
        self.start_doppler_btn.toggled.connect(self.on_toggle_doppler)

        sd_layout.addWidget(self.sdr_freq_label)
        sd_layout.addWidget(self.start_doppler_btn)

        from nast_gs.gui.sdr_panel import SDRPanel
        self.sdr_panel = SDRPanel()
        self.sdr_panel.device_started.connect(self._on_sdr_panel_started)
        self.sdr_panel.device_stopped.connect(self._on_sdr_panel_stopped)
        sd_layout.addWidget(self.sdr_panel)

        self.track_btn = QtWidgets.QPushButton("Start Tracking")
        self.track_btn.setCheckable(True)
        self.track_btn.toggled.connect(self._on_toggle_tracking)
        sd_layout.addWidget(self.track_btn)

        self.az_label = QtWidgets.QLabel("AZ: --°")
        self.el_label = QtWidgets.QLabel("EL: --°")
        self.range_label = QtWidgets.QLabel("Range: -- km")
        self.rate_label = QtWidgets.QLabel("Range rate: -- km/s")
        sd_layout.addWidget(self.az_label)
        sd_layout.addWidget(self.el_label)
        sd_layout.addWidget(self.range_label)
        sd_layout.addWidget(self.rate_label)

        self.ntp_label = QtWidgets.QLabel("NTP: --")
        self.use_ntp_chk = QtWidgets.QCheckBox("Use NTP time for tracking")
        self.ntp_sync_btn = QtWidgets.QPushButton("Sync NTP")
        self.ntp_sync_btn.clicked.connect(self._on_sync_ntp)
        sd_layout.addWidget(self.ntp_label)
        sd_layout.addWidget(self.use_ntp_chk)
        sd_layout.addWidget(self.ntp_sync_btn)

        self.rotor = SimulatedRotor()
        self._rotor_enabled = False
        self.rotor_btn = QtWidgets.QPushButton("Enable Rotor")
        self.rotor_btn.setCheckable(True)
        self.rotor_btn.toggled.connect(self._on_toggle_rotor)
        sd_layout.addWidget(self.rotor_btn)

        from nast_gs.gui.rotor_panel import RotorPanel
        self.rotor_panel = RotorPanel()
        sd_layout.addWidget(self.rotor_panel)

        controls_layout.addWidget(sd_widget)

        self._tracking_timer = QtCore.QTimer(self)
        self._tracking_timer.setInterval(1000)
        self._tracking_timer.timeout.connect(self._on_tracking_tick)

        # Status bar + bottom-right credit
        self.statusBar().showMessage("Ready")
        self._credit_lbl = QtWidgets.QLabel("Developed By Er. Damodar Pokhrel")
        self._credit_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.statusBar().addPermanentWidget(self._credit_lbl)

        # Load persisted config
        cfg = load_config() or {}
        lat = cfg.get("gs_lat", None)
        lon = cfg.get("gs_lon", None)
        alt = cfg.get("gs_alt", None)
        if lat is not None:
            self.tle_panel.gs_lat.setValue(float(lat))
        if lon is not None:
            self.tle_panel.gs_lon.setValue(float(lon))
        if alt is not None:
            self.tle_panel.gs_alt.setValue(float(alt))

        dl = cfg.get("downlink_hz", None)
        if dl is not None:
            try:
                self._downlink_hz = float(dl)
                self.doppler_ctrl = DopplerController(self.sdr, center_freq_hz=self._downlink_hz)
                self.sdr_freq_label.setText(f"SDR tuned: {self._downlink_hz/1e6:.6f} MHz")
            except Exception:
                pass

        # Park rotor at startup
        self._park_rotor(force=True)

    def _load_header_images(self):
        def set_pix(lbl: QtWidgets.QLabel, filename: str, height: int = 42):
            path = _asset_path(filename)
            pm = QtGui.QPixmap(path)
            if pm.isNull():
                lbl.setText(f"Missing: {filename}")
                return
            pm = pm.scaledToHeight(height, QtCore.Qt.TransformationMode.SmoothTransformation)
            lbl.setPixmap(pm)

        set_pix(self.nast_logo_lbl, "NASTLogo.png", 42)
        # IMPORTANT: this must match your exact filename in src/nast_gs/assets/
        set_pix(self.nepal_flag_lbl, "NEPALFlag.png", 42)
        

    def _open_about(self):
        AboutDialog(self).exec()

    def _park_rotor(self, force: bool = False):
        if (not force) and self._rotor_is_parked:
            return
        try:
            if getattr(self, "rotor_panel", None) and self.rotor_panel.has_rotor():
                self.rotor_panel.set_rotor_angle(self._park_az, self._park_el)
            else:
                self.rotor.set_az_el(self._park_az, self._park_el)
            self._rotor_is_parked = True
        except Exception:
            pass

    # ---------------- TLE propagate ----------------

    def on_propagate(self, opts: dict):
        tle = opts["tle"]
        downlink_hz = float(opts.get("downlink_hz", self._downlink_hz))
        self._downlink_hz = downlink_hz

        start = opts.get("start")
        if self.use_ntp_chk.isChecked() and self._ntp_time is not None:
            start = self._ntp_time

        pts = propagate_tle(
            tle,
            start,
            minutes=opts["minutes"],
            step_s=opts["step_s"],
            gs_lat=opts["gs_lat"],
            gs_lon=opts["gs_lon"],
            gs_alt_m=opts.get("gs_alt", 0.0),
        )

        latlon = [(p["sublat"], p["sublon"]) for p in pts]
        self.map.set_track(latlon)
        self.map.set_ground_station(opts["gs_lat"], opts["gs_lon"])

        self._current_tle = tle
        self._current_gs = (opts["gs_lat"], opts["gs_lon"])

        try:
            self.doppler_ctrl.center = self._downlink_hz
        except Exception:
            self.doppler_ctrl = DopplerController(self.sdr, center_freq_hz=self._downlink_hz)

        self.sdr_freq_label.setText(f"SDR tuned: {self._downlink_hz/1e6:.6f} MHz")

        try:
            if self.sdr_panel and getattr(self.sdr_panel, "sdr", None) is not None:
                self.sdr_panel.apply_doppler(self._downlink_hz)
        except Exception:
            pass

        cfg = load_config() or {}
        cfg["gs_lat"] = opts["gs_lat"]
        cfg["gs_lon"] = opts["gs_lon"]
        cfg["gs_alt"] = opts.get("gs_alt", 0.0)
        cfg["downlink_hz"] = float(self._downlink_hz)
        save_config(cfg)

    def on_toggle_doppler(self, checked: bool):
        self._doppler_enabled = checked

        if checked:
            if getattr(self.sdr_panel, "sdr", None) is None:
                try:
                    self.sdr_panel.start_btn.setChecked(True)
                except Exception:
                    pass

            if getattr(self.sdr_panel, "sdr", None) is not None:
                self.sdr = self.sdr_panel.sdr

            self.doppler_ctrl = DopplerController(self.sdr, center_freq_hz=self._downlink_hz)

            if self._current_tle is not None:
                self._tracking_timer.start()
        else:
            try:
                self._tracking_timer.stop()
            except Exception:
                pass

    def _on_tracking_tick(self):
        if not self._doppler_enabled or self._current_tle is None:
            return

        from datetime import datetime
        from nast_gs.prop.propagator import current_state

        gs_lat, gs_lon = self._current_gs

        now = datetime.utcnow()
        if self.use_ntp_chk.isChecked() and self._ntp_time is not None:
            now = self._ntp_time

        st = current_state(self._current_tle, now, gs_lat, gs_lon)
        rr = st.get("range_rate_km_s", 0.0)

        try:
            self.doppler_ctrl.center = self._downlink_hz
        except Exception:
            self.doppler_ctrl = DopplerController(self.sdr, center_freq_hz=self._downlink_hz)

        tuned_hz = self.doppler_ctrl.apply_correction(rr)
        self.sdr_freq_label.setText(f"SDR tuned: {tuned_hz/1e6:.6f} MHz")

        az = st.get("azdeg", 0.0)
        el = st.get("eldeg", 0.0)
        rng = st.get("range_km", 0.0)

        self.az_label.setText(f"AZ: {az:.2f}°")
        self.el_label.setText(f"EL: {el:.2f}°")
        self.range_label.setText(f"Range: {rng:.2f} km")
        self.rate_label.setText(f"Range rate: {rr:.4f} km/s")

        sublat = st.get("sublat", None)
        sublon = st.get("sublon", None)
        if sublat is not None and sublon is not None:
            self.map.set_satellite(sublat, sublon)

        try:
            if self.sdr_panel and getattr(self.sdr_panel, "sdr", None) is not None:
                self.sdr_panel.apply_doppler(tuned_hz)
        except Exception:
            pass

        if self._rotor_enabled:
            try:
                if el <= 0.0:
                    self._park_rotor(force=False)
                else:
                    self._rotor_is_parked = False
                    if getattr(self, "rotor_panel", None) and self.rotor_panel.has_rotor():
                        self.rotor_panel.set_rotor_angle(az, el)
                    else:
                        self.rotor.set_az_el(az, el)
            except Exception:
                pass

    def _on_toggle_rotor(self, checked: bool):
        self._rotor_enabled = checked
        if checked:
            self._park_rotor(force=True)

    def _on_toggle_tracking(self, checked: bool):
        if checked:
            if self._current_tle is None:
                QtWidgets.QMessageBox.warning(self, "No TLE", "Please load and propagate a TLE before starting tracking")
                self.track_btn.setChecked(False)
                return

            if not self.start_doppler_btn.isChecked():
                self.start_doppler_btn.setChecked(True)

            self._tracking_timer.start()
            self.statusBar().showMessage("Tracking started")
            self.track_btn.setText("Stop Tracking")
        else:
            self._tracking_timer.stop()
            self.statusBar().showMessage("Tracking stopped")
            self.track_btn.setText("Start Tracking")
            if self._rotor_enabled:
                self._park_rotor(force=True)

    def _on_sdr_panel_started(self, sdr_device):
        try:
            self.sdr = sdr_device
            self.doppler_ctrl = DopplerController(self.sdr, center_freq_hz=self._downlink_hz)
        except Exception:
            pass

    def _on_sdr_panel_stopped(self):
        try:
            self.sdr = SimulatedSDR()
            self.doppler_ctrl = DopplerController(self.sdr, center_freq_hz=self._downlink_hz)
        except Exception:
            pass

    def _on_sync_ntp(self):
        try:
            t = get_ntp_time()
            self._ntp_time = t
            self.ntp_label.setText(f"NTP: {t.isoformat()}")
            self.statusBar().showMessage("NTP sync successful")
        except Exception as e:
            self.statusBar().showMessage(f"NTP sync failed: {e}")



