import socket
import logging
from typing import Optional

from .device import SDRDevice

logger = logging.getLogger(__name__)


class GqrxDevice(SDRDevice):
    """
    Gqrx remote-control SDRDevice.

    Commands used:
      - Set frequency:  F <Hz>
      - Get frequency:  f
      - Set mode:       M <MODE>
      - Set bandwidth:  W <Hz>

    Note:
      - No IQ streaming (read_samples not supported)
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7356,
        timeout: float = 1.0,
        mode: str = "FM",
        bandwidth_hz: Optional[int] = None,
    ):
        self.addr = (host, int(port))
        self.timeout = float(timeout)

        self._freq: Optional[float] = None
        self._mode: str = str(mode).upper().strip()
        self._bw: Optional[int] = int(bandwidth_hz) if bandwidth_hz is not None else None

    def _cmd(self, cmd: str) -> str:
        with socket.create_connection(self.addr, timeout=self.timeout) as s:
            s.sendall((cmd + "\n").encode())
            return s.recv(1024).decode(errors="ignore").strip()

    def start(self):
        # Connectivity check
        self._cmd("f")
        logger.info("GqrxDevice: connected to %s:%s", self.addr[0], self.addr[1])

        # Apply initial mode/bandwidth
        if self._mode:
            try:
                self.set_mode(self._mode)
            except Exception as e:
                logger.warning("GqrxDevice: set_mode failed: %s", e)

        if self._bw is not None:
            try:
                self.set_bandwidth(self._bw)
            except Exception as e:
                logger.warning("GqrxDevice: set_bandwidth failed: %s", e)

    def stop(self):
        logger.info("GqrxDevice: stopped")

    def set_center_frequency(self, freq_hz: float) -> None:
        self._cmd(f"F {int(freq_hz)}")
        self._freq = float(freq_hz)

    def get_center_frequency(self) -> float:
        if self._freq is None:
            try:
                self._freq = float(self._cmd("f"))
            except Exception:
                return 0.0
        return float(self._freq)

    def read_samples(self, num_samples: int):
        raise NotImplementedError("Gqrx does not expose IQ samples via remote control")

    def set_mode(self, mode: str) -> None:
        m = str(mode).upper().strip()
        self._cmd(f"M {m}")
        self._mode = m

    def set_bandwidth(self, bw_hz: int) -> None:
        self._cmd(f"W {int(bw_hz)}")
        self._bw = int(bw_hz)
