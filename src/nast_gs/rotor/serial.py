"""Serial rotor controller implementations (Prosistel and generic command templates)."""

from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class SerialRotor:
    """Generic serial rotor controller. Uses a command template to send az/el commands.

    The template should be a Python format string with fields {az} and {el}, for example:
      "AZ{az:.1f};EL{el:.1f}\r"
    """

    def __init__(
        self,
        port: str,
        baud: int = 9600,
        timeout: float = 1.0,
        template: str = "AZ{az:.1f} EL{el:.1f}\r",
    ):
        self.port = port
        self.baud = int(baud)
        self.timeout = float(timeout)
        self.template = template
        self._serial = None

    def connect(self):
        try:
            import serial
        except Exception as e:
            raise RuntimeError("pyserial is required for serial rotor control; install with `pip install pyserial`") from e

        # Generic/default serial settings
        self._serial = serial.Serial(
            self.port,
            baudrate=self.baud,
            timeout=self.timeout,
        )
        logger.info(f"SerialRotor: connected to {self.port} @ {self.baud}")

    def disconnect(self):
        try:
            if self._serial and self._serial.is_open:
                self._serial.close()
        finally:
            self._serial = None

    def set_az_el(self, az_deg: float, el_deg: float) -> None:
        cmd = self.template.format(az=float(az_deg), el=float(el_deg))
        logger.info(f"SerialRotor: sending: {cmd!r}")
        if self._serial is None:
            raise RuntimeError("Serial rotor not connected")
        self._serial.write(cmd.encode("ascii", errors="ignore"))

    def park(self, az_deg: float = 100.0, el_deg: float = 90.0) -> None:
        """Send a park command to rotor (default AZ=100°, EL=90°)."""
        self.set_az_el(az_deg, el_deg)


class ProsistelRotor(SerialRotor):
    """Prosistel rotor command wrapper (C#-template compatible).

    This implementation matches the C# logic:
      - Send AZ command frame: [0x02]['A']['G'][ddd][t][0x0D]
      - Wait ~60 ms
      - Send EL command frame: [0x02]['B']['G'][ddd][t][0x0D]

    NOTE:
    - Uses integer degrees by default (tenths digit forced to '0'), same as safe mode.
    - If your controller truly supports tenths, you can change _encode_angle().
    """

    def __init__(
        self,
        port: str,
        baud: int = 9600,
        timeout: float = 1.0,
        inter_cmd_delay_s: float = 0.06,
    ):
        # keep parent init for compatibility; template is not used by Prosistel framing
        super().__init__(port, baud=baud, timeout=timeout, template="")
        self.inter_cmd_delay_s = float(inter_cmd_delay_s)

    def connect(self):
        try:
            import serial
        except Exception as e:
            raise RuntimeError("pyserial is required for serial rotor control; install with `pip install pyserial`") from e

        # Prosistel controllers are typically 9600 8N1, no flow control.
        self._serial = serial.Serial(
            self.port,
            baudrate=self.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout,
            rtscts=False,
            dsrdtr=False,
            xonxoff=False,
        )

        # Some adapters toggle these by default; force off (matches typical expectations)
        try:
            self._serial.dtr = False
            self._serial.rts = False
        except Exception:
            pass

        logger.info(f"ProsistelRotor: connected to {self.port} @ {self.baud}")

    def set_az_el(self, az_deg: float, el_deg: float) -> None:
        if self._serial is None or not getattr(self._serial, "is_open", False):
            raise RuntimeError("Prosistel rotor not connected")

        # clamp elevation like your C# logic
        if el_deg < 0:
            el_deg = 0.0

        # 1) AZ
        az_cmd = self._build_cmd(axis="A", angle_deg=float(az_deg))
        self._serial.write(az_cmd)

        # 2) delay (important)
        time.sleep(self.inter_cmd_delay_s)

        # 3) EL
        el_cmd = self._build_cmd(axis="B", angle_deg=float(el_deg))
        self._serial.write(el_cmd)

        logger.debug(
            "ProsistelRotor: sent AZ=%s EL=%s",
            az_cmd.hex(" "),
            el_cmd.hex(" "),
        )

    @staticmethod
    def _encode_angle(angle_deg: float) -> tuple[int, int, int, int]:
        """
        Return (hundreds, tens, ones, tenths) digits as integers 0-9.

        Safe default: integer degrees, tenths forced to 0.
        Matches the C# '... (int)(angle * 10) % 10 ...' but we force tenths=0 to avoid
        controllers that reject fractional mode.
        """
        deg_int = int(round(angle_deg))
        if deg_int < 0:
            deg_int = 0
        if deg_int > 359:
            deg_int = deg_int % 360

        h = (deg_int // 100) % 10
        t = (deg_int // 10) % 10
        o = (deg_int // 1) % 10
        tenths = 0
        return h, t, o, tenths

    def _build_cmd(self, axis: str, angle_deg: float) -> bytes:
        """
        Build Prosistel frame:
          [STX=0x02][axis]['G'][h][t][o][tenths][CR=0x0D]
        """
        if axis not in ("A", "B"):
            raise ValueError("axis must be 'A' (AZ) or 'B' (EL)")

        h, t, o, x = self._encode_angle(angle_deg)

        cmd = bytearray(8)
        cmd[0] = 0x02
        cmd[1] = ord(axis)
        cmd[2] = ord("G")
        cmd[3] = ord(str(h))
        cmd[4] = ord(str(t))
        cmd[5] = ord(str(o))
        cmd[6] = ord(str(x))
        cmd[7] = 0x0D
        return bytes(cmd)
