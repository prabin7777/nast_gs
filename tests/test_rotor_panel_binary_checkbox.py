from nast_gs.gui.rotor_panel import RotorPanel


def test_binary_checkbox_present(qtbot):
    panel = RotorPanel()
    assert hasattr(panel, 'binary_chk')
    assert panel.binary_chk.text().startswith('Use Prosistel binary')
