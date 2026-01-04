import pytest

# Skip GUI tests if PyQt6 is not available
pytest.importorskip("PyQt6")
from PyQt6 import QtWidgets


def test_apply_doppler_updates_freq(qtbot):
    from nast_gs.gui.sdr_panel import SDRPanel
    panel = SDRPanel()
    qtbot.addWidget(panel)
    panel.apply_doppler(146000000.0)
    assert abs(panel.freq_spin.value() - 146000000.0) < 1e-3


def test_demod_combo_has_expected_items(qtbot):
    from nast_gs.gui.sdr_panel import SDRPanel
    panel = SDRPanel()
    qtbot.addWidget(panel)
    items = [panel.demod_combo.itemText(i) for i in range(panel.demod_combo.count())]
    assert "FM" in items and "AM" in items and "CW" in items and "RTTY" in items
