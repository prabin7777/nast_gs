from PyQt6 import QtWidgets, QtCore
from .map_view import MapWindow
from .tle_panel import TLEPanel
from nast_gs.prop.propagator import propagate_tle
from nast_gs.sdr.device import SimulatedSDR
from nast_gs.sdr.doppler import DopplerController
from nast_gs.rotor.controller import SimulatedRotor
from nast_gs.config import load_config, save_config
from nast_gs.ntp import get_ntp_time


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Space Research Centre, Nepal Academy of Science and Technology (NAST) Ground Station")
        self.resize(1400, 900)

        central = QtWidgets.QWidget()
        central_layout = QtWidgets.QVBoxLayout(central)
        # reduce outer margins so the map can grow to the available area
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

        # center: map (centered)
        self.map = MapWindow()
        # let the map view expand to fill the center pane
        try:
            self.map.view.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        except Exception:
            pass
        center_container = QtWidgets.QWidget()
        center_layout = QtWidgets.QVBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        # allow the map view to fully expand in the center pane
        center_layout.addWidget(self.map.view, 1)
        # ensure the embedded view has a sensible minimum size so it is clearly visible
        try:
            self.map.view.setMinimumSize(600, 360)
        except Exception:
            pass
        splitter.addWidget(center_container)

        # right: controls container (scrollable)
        controls_widget = QtWidgets.QWidget()
        controls_layout = QtWidgets.QVBoxLayout(controls_widget)
        controls_layout.setContentsMargins(6, 6, 6, 6)
        # make SDR panel wider for a more formal presentation
        controls_widget.setMinimumWidth(320)
        controls_widget.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Expanding)
        right_scroll = QtWidgets.QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setWidget(controls_widget)
        splitter.addWidget(right_scroll)

        # make center expand by default and set reasonable initial sizes
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 3)  # center gets most of the extra space
        splitter.setStretchFactor(2, 0)
        # initial sizes: left narrow, center wider, right wider (more formal)
        try:
            splitter.setSizes([200, 880, 320])
        except Exception:
            pass

        central_layout.addWidget(splitter)
        self.setCentralWidget(central)

        self.tle_panel.propagate_requested.connect(self.on_propagate)
        # Simple SDR controls
        self.sdr = SimulatedSDR()
        self.doppler_ctrl = DopplerController(self.sdr, center_freq_hz=435_575_000.0)

        sd_widget = QtWidgets.QWidget()
        sd_layout = QtWidgets.QVBoxLayout(sd_widget)
        self.sdr_freq_label = QtWidgets.QLabel(f"SDR center: {self.sdr.get_center_frequency()/1e6:.6f} MHz")
        self.start_doppler_btn = QtWidgets.QPushButton("Start Doppler Updates")
        self.start_doppler_btn.setCheckable(True)
        self.start_doppler_btn.toggled.connect(self.on_toggle_doppler)
        sd_layout.addWidget(self.sdr_freq_label)
        sd_layout.addWidget(self.start_doppler_btn)
        # SDR panel
        from nast_gs.gui.sdr_panel import SDRPanel
        self.sdr_panel = SDRPanel()
        # connect signals so DopplerController follows the active device
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
        # add sd_widget to the right controls layout
        controls_layout.addWidget(sd_widget)

        self._doppler_enabled = False
        self._current_tle = None
        self._current_gs = (25.0, -80.0)
        self._tracking_timer = QtCore.QTimer(self)
        self._tracking_timer.setInterval(1000)
        self._tracking_timer.timeout.connect(self._on_tracking_tick)
        # rotor
        self.rotor = SimulatedRotor()
        self._rotor_enabled = False
        self.rotor_btn = QtWidgets.QPushButton("Enable Rotor")
        self.rotor_btn.setCheckable(True)
        self.rotor_btn.toggled.connect(self._on_toggle_rotor)
        sd_layout.addWidget(self.rotor_btn)
        # Rotor panel
        from nast_gs.gui.rotor_panel import RotorPanel
        self.rotor_panel = RotorPanel()
        sd_layout.addWidget(self.rotor_panel)
        # Pass prediction panel is now embedded in the TLE panel (left side)
        # status bar
        self.statusBar().showMessage("Ready")
        # load persisted config
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
        self._ntp_time = None

    def on_propagate(self, opts: dict):
        tle = opts["tle"]
        # choose time source (NTP if selected and available)
        start = opts.get("start")
        if self.use_ntp_chk.isChecked() and self._ntp_time is not None:
            start = self._ntp_time
        pts = propagate_tle(tle, start, minutes=opts["minutes"], step_s=opts["step_s"], gs_lat=opts["gs_lat"], gs_lon=opts["gs_lon"], gs_alt_m=opts.get("gs_alt", 0.0))
        latlon = [(p["sublat"], p["sublon"]) for p in pts]
        self.map.set_track(latlon)
        self.map.set_ground_station(opts["gs_lat"], opts["gs_lon"])
        # If doppler updates enabled, apply last point's correction
        if self._doppler_enabled and pts:
            last = pts[0]
            # use the instantaneous range rate from the first propagated point
            rr = last.get("range_rate_km_s", 0.0)
            newf = self.doppler_ctrl.apply_correction(rr)
            self.sdr_freq_label.setText(f"SDR center: {newf/1e6:.6f} MHz")
            # apply to SDR if panel has device
            try:
                if self.sdr_panel and self.sdr_panel.sdr is not None:
                    self.sdr_panel.apply_doppler(newf)
            except Exception:
                pass
        # store current TLE and GS for tracking
        self._current_tle = tle
        self._current_gs = (opts["gs_lat"], opts["gs_lon"])
        # Pass panel embedded in TLEPanel will be updated by TLEPanel._on_propagate
        # persist GS settings
        cfg = load_config()
        cfg["gs_lat"] = opts["gs_lat"]
        cfg["gs_lon"] = opts["gs_lon"]
        cfg["gs_alt"] = opts.get("gs_alt", 0.0)
        save_config(cfg)



        


    def on_toggle_doppler(self, checked: bool):
        self._doppler_enabled = checked
        if checked:
            # ensure an SDR device is running for doppler updates
            if getattr(self.sdr_panel, 'sdr', None) is None:
                # start panel device (this will emit device_started and rebind controller)
                try:
                    self.sdr_panel.start_btn.setChecked(True)
                except Exception:
                    pass
            else:
                # bind doppler controller to the panel device
                self.sdr = self.sdr_panel.sdr
                self.doppler_ctrl = DopplerController(self.sdr, center_freq_hz=self.sdr.get_center_frequency())
            # start tracking timer if we have a current TLE
            if self._current_tle is not None:
                self._tracking_timer.start()
        else:
            # stop doppler updates
            try:
                # if the panel device is running, keep it running but stop applying doppler
                self._tracking_timer.stop()
            except Exception:
                pass

    def _on_tracking_tick(self):
        # compute instantaneous state and apply doppler
        if not self._doppler_enabled or self._current_tle is None:
            return
        from datetime import datetime
        from nast_gs.prop.propagator import current_state

        gs_lat, gs_lon = self._current_gs
        # use NTP time if selected
        now = datetime.utcnow()
        if self.use_ntp_chk.isChecked() and self._ntp_time is not None:
            now = self._ntp_time
        st = current_state(self._current_tle, now, gs_lat, gs_lon)
        rr = st.get("range_rate_km_s", 0.0)
        newf = self.doppler_ctrl.apply_correction(rr)
        self.sdr_freq_label.setText(f"SDR center: {newf/1e6:.6f} MHz")
        # update telemetry labels
        az = st.get("azdeg", 0.0)
        el = st.get("eldeg", 0.0)
        rng = st.get("range_km", 0.0)
        self.az_label.setText(f"AZ: {az:.2f}°")
        self.el_label.setText(f"EL: {el:.2f}°")
        self.range_label.setText(f"Range: {rng:.2f} km")
        self.rate_label.setText(f"Range rate: {rr:.4f} km/s")
        # update satellite marker on map using subpoint
        from nast_gs.prop.propagator import current_state
        # current_state returns sublat/sublon
        sublat = st.get("sublat", None)
        sublon = st.get("sublon", None)
        if sublat is not None and sublon is not None:
            self.map.set_satellite(sublat, sublon)
        # update rotor if enabled and satellite is above horizon
        if self._rotor_enabled:
            az = st.get("azdeg", 0.0)
            el = st.get("eldeg", 0.0)
            # safety limit: do not command rotor if below horizon
            if el > 0.0:
                # prefer serial rotor panel if connected
                try:
                    if getattr(self, 'rotor_panel', None) and self.rotor_panel.has_rotor():
                        self.rotor_panel.set_rotor_angle(az, el)
                    else:
                        self.rotor.set_az_el(az, el)
                except Exception:
                    # keep going; don't crash the tracking
                    pass

    def _on_toggle_rotor(self, checked: bool):
        self._rotor_enabled = checked

    def _on_toggle_tracking(self, checked: bool):
        if checked:
            if self._current_tle is None:
                QtWidgets.QMessageBox.warning(self, "No TLE", "Please load and propagate a TLE before starting tracking")
                self.track_btn.setChecked(False)
                return
            # ensure doppler updates are enabled when starting tracking
            if not self.start_doppler_btn.isChecked():
                self.start_doppler_btn.setChecked(True)
            self._tracking_timer.start()
            self.statusBar().showMessage("Tracking started")
            self.track_btn.setText("Stop Tracking")
        else:
            self._tracking_timer.stop()
            self.statusBar().showMessage("Tracking stopped")
            self.track_btn.setText("Start Tracking")

    def _on_sdr_panel_started(self, sdr_device):
        """Rebind our DopplerController to the SDR device started in the panel."""
        try:
            self.sdr = sdr_device
            self.doppler_ctrl = DopplerController(self.sdr, center_freq_hz=self.sdr.get_center_frequency())
        except Exception:
            pass

    def _on_sdr_panel_stopped(self):
        """Restore default simulated SDR when panel device stops."""
        try:
            self.sdr = SimulatedSDR()
            self.doppler_ctrl = DopplerController(self.sdr, center_freq_hz=self.sdr.get_center_frequency())
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
