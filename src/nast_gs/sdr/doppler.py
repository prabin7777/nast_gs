"""Doppler calculation utilities and a simple controller to apply corrections to an SDR device."""
from typing import List


SPEED_OF_LIGHT = 299792458.0  # m/s


def doppler_shift_hz(center_freq_hz: float, range_rate_km_s: float) -> float:
    """Compute the Doppler-shifted observed frequency in Hz

    center_freq_hz: transmitter center frequency in Hz
    range_rate_km_s: positive when range increasing (satellite receding), in km/s

    Returns observed frequency in Hz.
    """
    # convert km/s to m/s
    vr = range_rate_km_s * 1000.0
    # relativistic correction negligible at these speeds; use non-relativistic approximation
    return center_freq_hz * (1.0 - (vr / SPEED_OF_LIGHT))


def freq_correction_hz(center_freq_hz: float, range_rate_km_s: float) -> float:
    """Return delta f (Hz) to apply to center frequency so the SDR tunes to compensate Doppler.

    If positive delta => tune upward, negative => tune downward.
    """
    obs = doppler_shift_hz(center_freq_hz, range_rate_km_s)
    return obs - center_freq_hz


class DopplerController:
    """Applies Doppler corrections to an SDRDevice based on a time series of range rates."""

    def __init__(self, sdr_device, center_freq_hz: float):
        self.sdr = sdr_device
        self.center = float(center_freq_hz)

    def apply_correction(self, range_rate_km_s: float):
        delta = freq_correction_hz(self.center, range_rate_km_s)
        new_freq = self.center + delta
        self.sdr.set_center_frequency(new_freq)
        return new_freq
