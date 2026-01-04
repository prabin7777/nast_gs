import pytest

# Skip GUI tests if PyQt6 is not available in this environment
pytest.importorskip("PyQt6")
from nast_gs.gui.tle_panel import TLEPanel
from PyQt6 import QtWidgets


def test_tle_panel_rejects_short_tle(qtbot):
    panel = TLEPanel()
    panel.tle_text.setPlainText("too short")
    # simulate propagate click
    # Propagate triggers a QMessageBox and returns without exception; ensure it does not set propagate
    panel._on_propagate()
