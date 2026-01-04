from nast_gs.sdr.doppler import doppler_shift_hz, freq_correction_hz, DopplerController
from nast_gs.sdr.device import SimulatedSDR


def test_doppler_shift_approaching():
    # Satellite approaching (negative range rate) should increase observed frequency
    f0 = 145_800_000.0
    vr = -0.2  # km/s approaching
    obs = doppler_shift_hz(f0, vr)
    assert obs > f0


def test_freq_correction_sign():
    f0 = 435_000_000.0
    vr = 0.1
    delta = freq_correction_hz(f0, vr)
    assert delta < 0  # receding -> observed frequency lower -> correction negative


def test_doppler_controller_applies_freq():
    sdr = SimulatedSDR(initial_freq_hz=145_800_000.0)
    ctrl = DopplerController(sdr, center_freq_hz=145_800_000.0)
    new_f = ctrl.apply_correction(-0.2)
    assert sdr.get_center_frequency() == new_f
