"""SoapySDR wrapper for hardware devices (USRP, RTL via Soapy modules)."""
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

try:
    import SoapySDR
    from SoapySDR import Device
except Exception:
    SoapySDR = None


def list_soapy_devices() -> List[dict]:
    """Return a list of available SoapySDR devices (info dicts)."""
    if SoapySDR is None:
        return []
    results = []
    devices = SoapySDR.Device.enumerate()
    for d in devices:
        results.append(d)
    return results


class SoapyDevice:
    def __init__(self, args: Optional[dict] = None):
        if SoapySDR is None:
            raise RuntimeError("SoapySDR not available; install soapysdr and modules")
        self.dev = Device(args or {})

    def set_center_frequency(self, freq_hz: float):
        # set for RX channel 0
        self.dev.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, float(freq_hz))

    def get_center_frequency(self) -> float:
        return float(self.dev.getFrequency(SoapySDR.SOAPY_SDR_RX, 0))

    def set_sample_rate(self, rate: float):
        self.dev.setSampleRate(SoapySDR.SOAPY_SDR_RX, 0, float(rate))

    def start(self):
        logger.info("SoapyDevice start called (streaming not implemented in wrapper)")

    def stop(self):
        logger.info("SoapyDevice stop called")
