"""SDR device base class and a simple simulated implementation for testing."""
from abc import ABC, abstractmethod
from typing import Optional
import logging


logger = logging.getLogger(__name__)


class SDRDevice(ABC):
    """Abstract SDR device interface."""

    @abstractmethod
    def set_center_frequency(self, freq_hz: float) -> None:
        """Set center frequency in Hz"""

    @abstractmethod
    def get_center_frequency(self) -> float:
        """Return current center frequency in Hz"""

    @abstractmethod
    def start(self):
        """Start streaming/samples (if applicable)"""

    @abstractmethod
    def stop(self):
        """Stop streaming/samples (if applicable)"""

    def read_samples(self, num_samples: int):
        """Read num_samples complex IQ samples (return numpy array) or raise NotImplementedError"""
        raise NotImplementedError()


class SimulatedSDR(SDRDevice):
    """Simulated SDR device for development and testing."""

    def __init__(self, initial_freq_hz: float = 435_575_000.0):
        self._freq = float(initial_freq_hz)
        self.running = False

    def set_center_frequency(self, freq_hz: float) -> None:
        logger.info(f"SimulatedSDR: setting freq to {freq_hz} Hz")
        self._freq = float(freq_hz)

    def get_center_frequency(self) -> float:
        return self._freq

    def start(self):
        self.running = True
        logger.info("SimulatedSDR: started")

    def read_samples(self, num_samples: int):
        """Generate synthetic complex samples at the current center frequency for testing streaming."""
        import numpy as np
        fs = 2400000.0
        t = np.arange(num_samples) / fs
        # generate a weak FM-like tone and a CW tone
        f = 1000.0
        phase = 2 * np.pi * f * t
        iq = 0.5 * np.exp(1j * phase)
        return iq

    def stop(self):
        self.running = False
        logger.info("SimulatedSDR: stopped")
