from nast_gs.rotor.controller import SimulatedRotor


def test_simulated_rotor_moves():
    r = SimulatedRotor()
    r.set_az_el(123.4, 45.6)
    assert abs(r.az - 123.4) < 1e-6
    assert abs(r.el - 45.6) < 1e-6


def test_simulated_rotor_parks_default():
    r = SimulatedRotor()
    r.park()
    assert abs(r.az - 100.0) < 1e-6
    assert abs(r.el - 90.0) < 1e-6
