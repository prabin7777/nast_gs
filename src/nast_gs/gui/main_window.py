from PyQt6 import QtWidgets, QtCore
from nast_gs.sdr.gqrx_launcher import ensure_gqrx_running

from .map_view import MapWindow
from .tle_panel import TLEPanel

from nast_gs.prop.propagator import propagate_tle
from nast_gs.sdr.device import SimulatedSDR
from nast_gs.sdr.doppler import DopplerController
from nast_gs.rotor.controller import SimulatedRotor
from nast_gs.config import load_config, save_config
from nast_gs.ntp import get_ntp_time


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

        self.setWindowTitle("Space Research Centre, Nepal Academy of Science and Technology (NAST) Ground Station")
        self.resize(1400, 900)


        central = QtWidgets.QWidget()
        central_layout = QtWidgets.QVBoxLayout(central)
        central_layout.setContentsMargins(2, 2, 2, 2)
        central_layout.setSpacing(4)

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

        central_layout.addWidget(splitter)
        self.setCentralWidget(central)

        # --- Signals ---
        self.tle_panel.propagate_requested.connect(self.on_propagate)

        # --- Runtime state ---
        self._doppler_enabled = False
        self._current_tle = None
        self._current_gs = (25.0, -80.0)
        self._downlink_hz = 145_800_000.0  # nominal downlink (single source of truth)
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

        # SDR panel (controls device selection + Gqrx mode/bw etc.)
        from nast_gs.gui.sdr_panel import SDRPanel
        self.sdr_panel = SDRPanel()
        self.sdr_panel.device_started.connect(self._on_sdr_panel_started)
        self.sdr_panel.device_stopped.connect(self._on_sdr_panel_stopped)
        sd_layout.addWidget(self.sdr_panel)

        # Tracking controls
        self.track_btn = QtWidgets.QPushButton("Start Tracking")
        self.track_btn.setCheckable(True)
        self.track_btn.toggled.connect(self._on_toggle_tracking)
        sd_layout.addWidget(self.track_btn)

        # Live telemetry labels
        self.az_label = QtWidgets.QLabel("AZ: --°")
        self.el_label = QtWidgets.QLabel("EL: --°")
        self.range_label = QtWidgets.QLabel("Range: -- km")
        self.rate_label = QtWidgets.QLabel("Range rate: -- km/s")
        sd_layout.addWidget(self.az_label)
        sd_layout.addWidget(self.el_label)
        sd_layout.addWidget(self.range_label)
        sd_layout.addWidget(self.rate_label)

        # NTP controls
        self.ntp_label = QtWidgets.QLabel("NTP: --")
        self.use_ntp_chk = QtWidgets.QCheckBox("Use NTP time for tracking")
        self.ntp_sync_btn = QtWidgets.QPushButton("Sync NTP")
        self.ntp_sync_btn.clicked.connect(self._on_sync_ntp)
        sd_layout.addWidget(self.ntp_label)
        sd_layout.addWidget(self.use_ntp_chk)
        sd_layout.addWidget(self.ntp_sync_btn)

        # Rotor
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

        # tracking timer
        self._tracking_timer = QtCore.QTimer(self)
        self._tracking_timer.setInterval(1000)
        self._tracking_timer.timeout.connect(self._on_tracking_tick)

        # status bar
        self.statusBar().showMessage("Ready")



    # Force a font that renders Latin digits consistently

        layout = QtWidgets.QFormLayout()
        # load persisted config (GS + optional last downlink)
        cfg = load_config()
        if cfg:
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

    # ---------------- TLE propagate ----------------

    def on_propagate(self, opts: dict):
        tle = opts["tle"]

        # single frequency: nominal downlink provided by TLE panel
        # expects opts["downlink_hz"]; fallback if older panel doesn't send it
        downlink_hz = float(opts.get("downlink_hz", self._downlink_hz))
        self._downlink_hz = downlink_hz

        # choose time source (NTP if selected and available)
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

        # map track + GS
        latlon = [(p["sublat"], p["sublon"]) for p in pts]
        self.map.set_track(latlon)
        self.map.set_ground_station(opts["gs_lat"], opts["gs_lon"])

        # store current TLE and GS for tracking
        self._current_tle = tle
        self._current_gs = (opts["gs_lat"], opts["gs_lon"])

        # bind doppler to nominal downlink (IMPORTANT: stable reference)
        try:
            self.doppler_ctrl.center = self._downlink_hz
        except Exception:
            self.doppler_ctrl = DopplerController(self.sdr, center_freq_hz=self._downlink_hz)

        # update label to nominal immediately
        self.sdr_freq_label.setText(f"SDR tuned: {self._downlink_hz/1e6:.6f} MHz")

        # if an SDR device is running, tune it to nominal right away (before doppler ticks)
        try:
            if self.sdr_panel and getattr(self.sdr_panel, "sdr", None) is not None:
                self.sdr_panel.apply_doppler(self._downlink_hz)
        except Exception:
            pass

        # persist GS + downlink
        cfg = load_config()
        cfg["gs_lat"] = opts["gs_lat"]
        cfg["gs_lon"] = opts["gs_lon"]
        cfg["gs_alt"] = opts.get("gs_alt", 0.0)
        cfg["downlink_hz"] = float(self._downlink_hz)
        save_config(cfg)

    # ---------------- Doppler enable/disable ----------------

    def on_toggle_doppler(self, checked: bool):
        self._doppler_enabled = checked

        if checked:
            # ensure an SDR device is running for doppler updates
            if getattr(self.sdr_panel, "sdr", None) is None:
                try:
                    self.sdr_panel.start_btn.setChecked(True)
                except Exception:
                    pass

            # rebind to panel SDR if available
            if getattr(self.sdr_panel, "sdr", None) is not None:
                self.sdr = self.sdr_panel.sdr

            # always use nominal downlink as doppler reference
            self.doppler_ctrl = DopplerController(self.sdr, center_freq_hz=self._downlink_hz)

            # start tracking timer if we have a current TLE
            if self._current_tle is not None:
                self._tracking_timer.start()
        else:
            try:
                self._tracking_timer.stop()
            except Exception:
                pass

    # ---------------- Live tracking tick ----------------

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

        # IMPORTANT: keep reference fixed to nominal downlink
        try:
            self.doppler_ctrl.center = self._downlink_hz
        except Exception:
            self.doppler_ctrl = DopplerController(self.sdr, center_freq_hz=self._downlink_hz)

        tuned_hz = self.doppler_ctrl.apply_correction(rr)
        self.sdr_freq_label.setText(f"SDR tuned: {tuned_hz/1e6:.6f} MHz")

        # update telemetry labels
        az = st.get("azdeg", 0.0)
        el = st.get("eldeg", 0.0)
        rng = st.get("range_km", 0.0)

        self.az_label.setText(f"AZ: {az:.2f}°")
        self.el_label.setText(f"EL: {el:.2f}°")
        self.range_label.setText(f"Range: {rng:.2f} km")
        self.rate_label.setText(f"Range rate: {rr:.4f} km/s")

        # update satellite marker on map using subpoint
        sublat = st.get("sublat", None)
        sublon = st.get("sublon", None)
        if sublat is not None and sublon is not None:
            self.map.set_satellite(sublat, sublon)

        # apply to SDR device via SDR panel
        try:
            if self.sdr_panel and getattr(self.sdr_panel, "sdr", None) is not None:
                self.sdr_panel.apply_doppler(tuned_hz)
        except Exception:
            pass

        # update rotor if enabled and satellite is above horizon
        # update rotor if enabled
        if self._rotor_enabled:
           try:
               if el <= 0.0:
                   # Satellite below horizon -> park once and hold
                   if not self._rotor_is_parked:
                       if getattr(self, "rotor_panel", None) and self.rotor_panel.has_rotor():
                           # Prefer hardware park if available
                           try:
                               self.rotor_panel._rotor.park()
                           except Exception:
                               # Fallback park angle if park() is not implemented
                               self.rotor_panel.set_rotor_angle(0.0, 90.0)
                       else:
                           # Simulated fallback park
                           self.rotor.set_az_el(0.0, 90.0)
        
                       self._rotor_is_parked = True
        
               else:
                   # Satellite above horizon -> track
                   self._rotor_is_parked = False
        
                   if getattr(self, "rotor_panel", None) and self.rotor_panel.has_rotor():
                       self.rotor_panel.set_rotor_angle(az, el)
                   else:
                       self.rotor.set_az_el(az, el)
        
           except Exception:
               pass

    # ---------------- Rotor + Tracking buttons ----------------

    def _on_toggle_rotor(self, checked: bool):
        self._rotor_enabled = checked

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

    # ---------------- SDR panel callbacks ----------------

    def _on_sdr_panel_started(self, sdr_device):
        # bind controller to selected SDR device, but keep nominal downlink reference
        try:
            self.sdr = sdr_device
            self.doppler_ctrl = DopplerController(self.sdr, center_freq_hz=self._downlink_hz)
        except Exception:
            pass

    def _on_sdr_panel_stopped(self):
        # fallback to simulated SDR, keep nominal downlink reference
        try:
            self.sdr = SimulatedSDR()
            self.doppler_ctrl = DopplerController(self.sdr, center_freq_hz=self._downlink_hz)
        except Exception:
            pass

    # ---------------- NTP ----------------

    def _on_sync_ntp(self):
        try:
            t = get_ntp_time()
            self._ntp_time = t
            self.ntp_label.setText(f"NTP: {t.isoformat()}")
            self.statusBar().showMessage("NTP sync successful")
        except Exception as e:
            self.statusBar().showMessage(f"NTP sync failed: {e}")
