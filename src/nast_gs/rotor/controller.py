"""Rotor controller abstraction and a simulated implementation."""
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class RotorController(ABC):
    @abstractmethod
    def set_az_el(self, az_deg: float, el_deg: float) -> None:
        """Set rotor position in degrees."""
    def park(self, az_deg: float = 100.0, el_deg: float = 90.0) -> None:
        """Park rotor to a safe position (defaults to AZ=100°, EL=90°)."""
        # default implementation uses set_az_el
        self.set_az_el(az_deg, el_deg)


class SimulatedRotor(RotorController):
    def __init__(self):
        self.az = 0.0
        self.el = 0.0

    def set_az_el(self, az_deg: float, el_deg: float) -> None:
        logger.info(f"SimulatedRotor: moving to AZ={az_deg:.2f} EL={el_deg:.2f}")
        self.az = float(az_deg)
        self.el = float(el_deg)

    def park(self, az_deg: float = 100.0, el_deg: float = 90.0) -> None:
        logger.info(f"SimulatedRotor: parking to AZ={az_deg:.2f} EL={el_deg:.2f}")
        self.set_az_el(az_deg, el_deg)
