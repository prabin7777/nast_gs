"""RTL-SDR device wrapper using pyrtlsdr."""

import logging
from typing import Optional

import numpy as np

from .device import SDRDevice

logger = logging.getLogger(__name__)

try:
    from rtlsdr import RtlSdr
    from rtlsdr.rtlsdr import LibUSBError
except Exception:
    RtlSdr = None
    LibUSBError = Exception


class RtlSdrDevice(SDRDevice):
    def __init__(
        self,
        device_index: int = 0,
        sample_rate: float = 2.4e6,
        gain: Optional[float] = None,
        ppm: float = 0.0,
    ):
        if RtlSdr is None:
            raise RuntimeError("pyrtlsdr not installed. Install with: pip install pyrtlsdr")

        self.device_index = int(device_index)
        self._sr = float(sample_rate)
        self._gain = gain
        self._ppm = float(ppm)

        self.sdr = RtlSdr(device_index=self.device_index)

        # Sample rate
        self.sdr.sample_rate = self._sr

        # PPM correction (some librtlsdr builds return INVALID_PARAM even for 0)
        try:
            ppm_int = int(round(self._ppm))
            if ppm_int != 0:
                self.sdr.freq_correction = ppm_int
        except Exception as e:
            logger.warning(
                "RTL-SDR: PPM correction not supported/failed (%s). Continuing without PPM.",
                e,
            )

        # Gain
        if self._gain is None:
            try:
                self.sdr.gain = "auto"
            except Exception:
                pass
        else:
            self.sdr.gain = float(self._gain)

        self._running = False

    def set_sample_rate(self, rate: float):
        self._sr = float(rate)
        self.sdr.sample_rate = self._sr

    def set_center_frequency(self, freq_hz: float) -> None:
        self.sdr.center_freq = float(freq_hz)

    def get_center_frequency(self) -> float:
        return float(self.sdr.center_freq)

    def start(self):
        self._running = True
        try:
            self.sdr.reset_buffer()
        except Exception:
            pass
        logger.info("RtlSdrDevice: started")

    def read_samples(self, num_samples: int):
        if not self._running:
            self.start()

        try:
            iq = self.sdr.read_samples(int(num_samples))
            return np.asarray(iq, dtype=np.complex64)

        except LibUSBError as e:
            self._running = False
            raise RuntimeError(f"RTL-SDR USB error: {e}") from e

        except Exception:
            self._running = False
            raise

    def stop(self):
        self._running = False
        try:
            self.sdr.close()
        except Exception:
            pass
        logger.info("RtlSdrDevice: stopped")
