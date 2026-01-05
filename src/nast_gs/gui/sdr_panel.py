from __future__ import annotations

from PyQt6 import QtWidgets, QtCore
from typing import Optional, List
import numpy as np

from nast_gs.sdr import list_soapy_devices, SoapyDevice, RtlSdrDevice, SimulatedSDR
from nast_gs.sdr.doppler import DopplerController
from nast_gs.sdr.streamer import SDRStreamer
from nast_gs.gui.spectrum_widget import SpectrumWidget

from nast_gs.demod.fm import fm_demod_to_audio
from nast_gs.demod.cw import cw_demod


# Optional Gqrx backend
try:
    from nast_gs.sdr.gqrx import GqrxDevice
except Exception:
    GqrxDevice = None


class SDRPanel(QtWidgets.QWidget):
    """UI panel to select SDR device, set freq/sample rate, and start/stop device."""
    device_started = QtCore.pyqtSignal(object)
    device_stopped = QtCore.pyqtSignal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)


        self._en_loc = QtCore.QLocale(QtCore.QLocale.Language.English, QtCore.QLocale.Country.UnitedStates)
        self.setLocale(self._en_loc)

        layout = QtWidgets.QFormLayout()

        self.device_combo = QtWidgets.QComboBox()
        self.refresh_btn = QtWidgets.QPushButton("Refresh Devices")
        self.refresh_btn.clicked.connect(self._refresh)

        # IMPORTANT: this is your nominal / tuned center frequency (Hz).
        self.freq_spin = QtWidgets.QDoubleSpinBox()
        self.freq_spin.setRange(100e3, 6e9)
        self.freq_spin.setDecimals(0)
        self.freq_spin.setValue(437_345_000.0) ###
        self.freq_spin.setSuffix(" Hz")

        self.samplerate_spin = QtWidgets.QDoubleSpinBox()
        self.samplerate_spin.setRange(50e3, 20e6)
        self.samplerate_spin.setDecimals(0)
        self.samplerate_spin.setValue(2_400_000.0)
        self.samplerate_spin.setSuffix(" sps")

        # Gqrx remote control fields
        self.gqrx_host = QtWidgets.QLineEdit("127.0.0.1")
        self.gqrx_port = QtWidgets.QSpinBox()
        self.gqrx_port.setRange(1, 65535)
        self.gqrx_port.setValue(7356)

        self.bandwidth_spin = QtWidgets.QSpinBox()
        self.bandwidth_spin.setRange(100, 5_000_000)
        self.bandwidth_spin.setValue(12_000)
        self.bandwidth_spin.setSuffix(" Hz")

        self.start_btn = QtWidgets.QPushButton("Start Device")
        self.start_btn.setCheckable(True)
        self.start_btn.toggled.connect(self._on_toggle)

        # Demod controls (IQ backends only). For Gqrx, we use this dropdown to command Gqrx mode.
        self.play_audio_btn = QtWidgets.QPushButton("Play Demod Audio")
        self.play_audio_btn.setCheckable(True)
        self.play_audio_btn.toggled.connect(self._on_audio_toggle)

        self.demod_combo = QtWidgets.QComboBox()
        self.demod_combo.addItems(["FM", "AM", "CW", "RTTY"])
        self.demod_combo.currentTextChanged.connect(self._on_demod_changed)

        self.rtty_out = QtWidgets.QTextEdit()
        self.rtty_out.setReadOnly(True)
        self.rtty_out.setMaximumHeight(80)

        # Save buttons (IQ backends only)
        self.save_iq_btn = QtWidgets.QPushButton("Save IQ")
        self.save_iq_btn.clicked.connect(self._on_save_iq)
        self.save_audio_btn = QtWidgets.QPushButton("Save Audio")
        self.save_audio_btn.clicked.connect(self._on_save_audio)

        # Spectrum (IQ backends only)
        self.spectrum = SpectrumWidget()
        self.open_spec_btn = QtWidgets.QPushButton("Open Spectrum Window")
        self.open_spec_btn.clicked.connect(self._open_spectrum_window)

        layout.addRow(self.device_combo, self.refresh_btn)
        layout.addRow("Center frequency:", self.freq_spin)
        layout.addRow("Sample rate:", self.samplerate_spin)

        layout.addRow("Gqrx host:", self.gqrx_host)
        layout.addRow("Gqrx port:", self.gqrx_port)
        layout.addRow("Bandwidth:", self.bandwidth_spin)

        layout.addRow(self.start_btn)
        layout.addRow(self.spectrum)
        layout.addRow(self.open_spec_btn)
        layout.addRow(self.save_iq_btn, self.save_audio_btn)
        layout.addRow(self.play_audio_btn)
        layout.addRow("Mode/Demod:", self.demod_combo)
        layout.addRow(QtWidgets.QLabel("RTTY/Decoded output:"), self.rtty_out)

        self.setLayout(layout)

        # runtime
        self.sdr = None
        self.doppler: Optional[DopplerController] = None
        self.streamer: Optional[SDRStreamer] = None
        self._spec_timer: Optional[QtCore.QTimer] = None
        self.last_samples: Optional[np.ndarray] = None
        self.spec_window = None

        # audio runtime
        self._audio_stream = None
        self._audio_q: List[np.ndarray] = []
        self._audio_fs = 48000

        self.device_combo.currentTextChanged.connect(self._on_backend_changed)

        self._refresh()
        self._on_backend_changed(self.device_combo.currentText())

    # ---------------- device list ----------------

    def _refresh(self):
        self.device_combo.clear()

        for d in list_soapy_devices():
            desc = d.get("driver", str(d))
            self.device_combo.addItem(f"Soapy: {desc}")

        if RtlSdrDevice is not None:
            self.device_combo.addItem("RTL-SDR")

        if GqrxDevice is not None:
            self.device_combo.addItem("GQRX (external)")

        self.device_combo.addItem("Simulated")

    def _on_backend_changed(self, txt: str):
        is_gqrx = (txt == "GQRX (external)")

        # Gqrx does not support IQ streaming in our app
        self.samplerate_spin.setEnabled(not is_gqrx)
        self.spectrum.setEnabled(not is_gqrx)
        self.open_spec_btn.setEnabled(not is_gqrx)
        self.save_iq_btn.setEnabled(not is_gqrx)
        self.save_audio_btn.setEnabled(not is_gqrx)
        self.play_audio_btn.setEnabled(not is_gqrx)

        # Gqrx remote fields enabled only for Gqrx
        self.gqrx_host.setEnabled(is_gqrx)
        self.gqrx_port.setEnabled(is_gqrx)
        self.bandwidth_spin.setEnabled(is_gqrx)

        # Mode dropdown is used for both:
        # - IQ backends: demod inside python
        # - Gqrx backend: command Gqrx mode
        self.demod_combo.setEnabled(True)

    # ---------------- start/stop ----------------

    def _on_toggle(self, checked: bool):
        if checked:
            self.start_btn.setText("Stop Device")
            self._start_device()
        else:
            self.start_btn.setText("Start Device")
            self._stop_device()

    def _start_device(self):
        sel = self.device_combo.currentText()
        try:
            cf = float(self.freq_spin.value())
            sr = float(self.samplerate_spin.value())
            bw = int(self.bandwidth_spin.value())
            mode = self.demod_combo.currentText()

            # IMPORTANT: stop any previous state (safety)
            self._stop_device_internal(emit=False)

            if sel.startswith("Soapy"):
                self.sdr = SoapyDevice()
                self.sdr.set_center_frequency(cf)
                try:
                    self.sdr.set_sample_rate(sr)
                except Exception:
                    pass
                self.sdr.start()

                self.doppler = DopplerController(self.sdr, center_freq_hz=cf)

                self.streamer = SDRStreamer(self.sdr, sample_rate=sr, block_size=8192)
                self.streamer.start()
                self._start_spec_timer()

            elif sel == "RTL-SDR":
                # This will FAIL if Gqrx is already using the dongle (LIBUSB_BUSY).
                self.sdr = RtlSdrDevice(ppm=0)
                self.sdr.set_center_frequency(cf)
                try:
                    self.sdr.set_sample_rate(sr)
                except Exception:
                    pass
                self.sdr.start()

                self.doppler = DopplerController(self.sdr, center_freq_hz=cf)

                self.streamer = SDRStreamer(self.sdr, sample_rate=sr, block_size=8192)
                self.streamer.start()
                self._start_spec_timer()

            elif sel == "GQRX (external)":
                if GqrxDevice is None:
                    raise RuntimeError("Gqrx backend not available (import failed).")

                host = self.gqrx_host.text().strip() or "127.0.0.1"
                port = int(self.gqrx_port.value())

                # Create Gqrx device. Some older versions may not accept mode/bandwidth args.
                try:
                    self.sdr = GqrxDevice(host=host, port=port, mode=self._map_mode_for_gqrx(mode), bandwidth_hz=bw)
                except TypeError:
                    self.sdr = GqrxDevice(host=host, port=port)

                self.sdr.start()

                # Apply mode/bandwidth if methods exist
                self._apply_gqrx_mode_bw()

                # Apply initial frequency
                self.sdr.set_center_frequency(cf)

                # Doppler will retune by calling set_center_frequency()
                self.doppler = DopplerController(self.sdr, center_freq_hz=cf)

                # CRITICAL: no IQ streamer for Gqrx, otherwise you go back to RTL busy/IQ logic.
                self.streamer = None
                self._stop_spec_timer()
                self.last_samples = None

            else:
                self.sdr = SimulatedSDR()
                self.sdr.set_center_frequency(cf)
                try:
                    self.sdr.set_sample_rate(sr)
                except Exception:
                    pass
                self.sdr.start()

                self.doppler = DopplerController(self.sdr, center_freq_hz=cf)

                self.streamer = SDRStreamer(self.sdr, sample_rate=sr, block_size=8192)
                self.streamer.start()
                self._start_spec_timer()

            try:
                self.device_started.emit(self.sdr)
            except Exception:
                pass

        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "SDR Error", str(e))
            self.start_btn.setChecked(False)

    def _stop_device(self):
        self._stop_device_internal(emit=True)

    def _stop_device_internal(self, emit: bool):
        self._stop_spec_timer()
        self._stop_audio_stream()

        if self.streamer is not None:
            try:
                self.streamer.stop()
            except Exception:
                pass
            self.streamer = None

        if self.sdr is not None:
            try:
                self.sdr.stop()
            except Exception:
                pass
            self.sdr = None

        self.doppler = None
        self.last_samples = None

        if emit:
            try:
                self.device_stopped.emit()
            except Exception:
                pass

    def _start_spec_timer(self):
        self._spec_timer = QtCore.QTimer(self)
        self._spec_timer.setInterval(10)
        self._spec_timer.timeout.connect(self._on_spec_poll)
        self._spec_timer.start()

    def _stop_spec_timer(self):
        if self._spec_timer is not None:
            try:
                self._spec_timer.stop()
            except Exception:
                pass
            self._spec_timer = None

    # ---------------- doppler integration ----------------

    def apply_doppler(self, new_freq_hz: float):
        # Called from main_window doppler/tick path.
        if self.sdr:
            try:
                self.sdr.set_center_frequency(float(new_freq_hz))
            except Exception:
                pass

        # Update display
        try:
            self.freq_spin.setValue(float(new_freq_hz))
        except Exception:
            pass

        # Keep doppler controller centered around whatever we are using now
        if self.doppler is not None:
            try:
                self.doppler.center = float(new_freq_hz)
            except Exception:
                pass

    # ---------------- Gqrx helpers ----------------

    def _map_mode_for_gqrx(self, mode: str) -> str:
        # Gqrx does not have "RTTY" mode. For RTTY (AFSK), USB is common.
        m = (mode or "FM").upper().strip()
        if m == "RTTY":
            return "USB"
        if m in ("FM", "AM", "CW", "USB", "LSB"):
            return m
        return "FM"

    def _apply_gqrx_mode_bw(self):
        if self.sdr is None:
            return
        if self.device_combo.currentText() != "GQRX (external)":
            return

        mode = self._map_mode_for_gqrx(self.demod_combo.currentText())
        bw = int(self.bandwidth_spin.value())

        # call only if supported
        try:
            if hasattr(self.sdr, "set_mode"):
                self.sdr.set_mode(mode)
        except Exception:
            pass

        try:
            if hasattr(self.sdr, "set_bandwidth"):
                self.sdr.set_bandwidth(bw)
        except Exception:
            pass

    def _on_demod_changed(self, _txt: str):
        # If Gqrx backend is active, switching dropdown should command Gqrx mode immediately.
        if self.device_combo.currentText() == "GQRX (external)" and self.sdr is not None:
            self._apply_gqrx_mode_bw()

    # ---------------- spectrum + demod (IQ backends only) ----------------

    def _on_spec_poll(self):
        if not self.streamer:
            return

        try:
            samples = self.streamer.out_q.get_nowait()
        except Exception:
            return

        self.last_samples = samples

        try:
            center = float(self.sdr.get_center_frequency())
        except Exception:
            center = float(self.freq_spin.value())

        sr = float(self.samplerate_spin.value())

        self.spectrum.update_from_iq(samples, center_hz=center, sample_rate=sr)

        try:
            if self.spec_window is not None:
                self.spec_window.update_from_iq(samples, center_hz=center, sample_rate=sr)
        except Exception:
            pass

        # Python demod only for IQ backends
        if self.play_audio_btn.isChecked():
            dem = self.demod_combo.currentText()

            if dem == "FM":
                try:
                    audio = fm_demod_to_audio(
                        samples,
                        fs=sr,
                        center_offset_hz=0.0,
                        chan_bw_hz=2e3,
                        audio_fs=self._audio_fs,
                        deemph_tau=75e-6,
                    )
                    self._push_audio(audio)
                except Exception:
                    pass

            elif dem == "AM":
                from nast_gs.demod.am import am_demod
                try:
                    audio = am_demod(samples[:8192])
                    audio = self._resample_audio(audio, sr, self._audio_fs)
                    self._push_audio(audio)
                except Exception:
                    pass

            elif dem == "CW":
                try:
                    audio = cw_demod(samples[:8192])
                    audio = self._resample_audio(audio, sr, self._audio_fs)
                    self._push_audio(audio)
                except Exception:
                    pass

            elif dem == "RTTY":
                from nast_gs.demod.rtty import rtty_demod
                try:
                    res = rtty_demod(samples[:8192])
                    self.rtty_out.setPlainText(res.get("text", "") or f"Status: {res.get('status')}")
                except Exception:
                    pass

    # ---------------- audio stream handling (IQ backends only) ----------------

    def _on_audio_toggle(self, checked: bool):
        if checked:
            self._ensure_audio_stream()
        else:
            self._stop_audio_stream()

    def _ensure_audio_stream(self):
        if self._audio_stream is not None:
            return
        try:
            import sounddevice as sd
        except Exception:
            return

        self._audio_q = []

        def cb(outdata, frames, time_info, status):
            if self._audio_q:
                blk = self._audio_q.pop(0)
                if blk.ndim == 1:
                    blk = blk.reshape(-1, 1)
                n = min(frames, blk.shape[0])
                outdata[:n, 0] = blk[:n, 0]
                if n < frames:
                    outdata[n:, 0] = 0.0
            else:
                outdata[:, 0] = 0.0

        self._audio_stream = sd.OutputStream(
            samplerate=self._audio_fs,
            channels=1,
            dtype="float32",
            blocksize=1024,
            callback=cb,
        )
        self._audio_stream.start()

    def _stop_audio_stream(self):
        if self._audio_stream is None:
            return
        try:
            self._audio_stream.stop()
            self._audio_stream.close()
        except Exception:
            pass
        self._audio_stream = None
        self._audio_q = []

    def _push_audio(self, audio: np.ndarray):
        if audio is None:
            return
        self._ensure_audio_stream()
        if self._audio_stream is None:
            return

        audio = np.asarray(audio, dtype=np.float32)
        if audio.ndim != 1:
            audio = audio.reshape(-1)

        m = float(np.max(np.abs(audio)) + 1e-12)
        audio = audio / m

        self._audio_q.append(audio)
        if len(self._audio_q) > 20:
            self._audio_q = self._audio_q[-10:]

    def _resample_audio(self, audio: np.ndarray, fs_in: float, fs_out: int) -> np.ndarray:
        audio = np.asarray(audio, dtype=np.float32)
        if int(fs_in) == int(fs_out):
            return audio
        try:
            from scipy.signal import resample_poly
            return resample_poly(audio, fs_out, int(fs_in)).astype(np.float32)
        except Exception:
            decim = max(1, int(fs_in / fs_out))
            return audio[::decim].astype(np.float32)

    # ---------------- save IQ/audio ----------------

    def _on_save_iq(self):
        if self.last_samples is None:
            QtWidgets.QMessageBox.information(self, "No samples", "No IQ samples available to save")
            return
        fn, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save IQ samples", "iq_samples.npy", "NumPy files (*.npy)")
        if fn:
            np.save(fn, self.last_samples)

    def _on_save_audio(self):
        if self.last_samples is None:
            QtWidgets.QMessageBox.information(self, "No samples", "No IQ samples available to save")
            return

        fn, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save demodulated audio", "audio.wav", "WAV files (*.wav)")
        if not fn:
            return

        try:
            from scipy.io.wavfile import write
        except Exception:
            QtWidgets.QMessageBox.warning(self, "Save Audio", "scipy is required to save WAV. Install: pip install scipy")
            return

        sr_dev = float(self.samplerate_spin.value())
        dem = self.demod_combo.currentText()

        if dem == "FM":
            try:
                audio = fm_demod_to_audio(
                    self.last_samples,
                    fs=sr_dev,
                    center_offset_hz=0.0,
                    chan_bw_hz=15e3,
                    audio_fs=self._audio_fs,
                    deemph_tau=75e-6,
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Save Audio", str(e))
                return
        elif dem == "AM":
            from nast_gs.demod.am import am_demod
            audio = am_demod(self.last_samples[:8192])
            audio = self._resample_audio(audio, sr_dev, self._audio_fs)
        elif dem == "CW":
            audio = cw_demod(self.last_samples[:8192])
            audio = self._resample_audio(audio, sr_dev, self._audio_fs)
        else:
            QtWidgets.QMessageBox.information(self, "No audio", "RTTY does not output audio in this demo")
            return

        audio = np.asarray(audio, dtype=np.float32)
        audio = audio / (np.max(np.abs(audio)) + 1e-12)
        audio16 = (audio * 0.9 * 32767).astype(np.int16)
        write(fn, self._audio_fs, audio16)

    # ---------------- spectrum window ----------------

    def _open_spectrum_window(self):
        if self.spec_window is None:
            from nast_gs.gui.spectrum_window import SpectrumWindow
            self.spec_window = SpectrumWindow()
        self.spec_window.show()
