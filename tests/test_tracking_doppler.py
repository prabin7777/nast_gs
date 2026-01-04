import pytest

pytest.importorskip("PyQt6")
from PyQt6 import QtWidgets
from nast_gs.gui.main_window import MainWindow
from nast_gs.prop import load_tle
from pathlib import Path


def test_mainwindow_rebinds_doppler_on_panel_start(qtbot):
    mw = MainWindow()
    qtbot.addWidget(mw)
    # initially doppler controller bound to mw.sdr
    assert mw.doppler_ctrl.sdr is mw.sdr
    # ensure we use simulated device and start panel device (use click and wait)
    mw.sdr_panel.device_combo.setCurrentText("Simulated")
    mw.sdr_panel.start_btn.click()
    qtbot.waitUntil(lambda: getattr(mw.sdr_panel, 'sdr', None) is not None, timeout=1000)
    # after device start, controller should be rebinding to panel device
    assert mw.doppler_ctrl.sdr is mw.sdr_panel.sdr


def test_tracking_applies_doppler_to_panel_device(qtbot):
    mw = MainWindow()
    qtbot.addWidget(mw)
    tle_path = Path(__file__).resolve().parents[1] / "data" / "iss.tle"
    tle = load_tle(str(tle_path))
    # start the panel device and wait
    mw.sdr_panel.device_combo.setCurrentText("Simulated")
    mw.sdr_panel.start_btn.click()
    qtbot.waitUntil(lambda: getattr(mw.sdr_panel, 'sdr', None) is not None, timeout=1000)
    # enable doppler updates
    mw.start_doppler_btn.click()
    # propagate (this should compute an initial correction and apply to panel)
    from datetime import datetime
    opts = dict(tle=tle, minutes=10, step_s=60, gs_lat=0.0, gs_lon=0.0, start=datetime.utcnow())
    mw.on_propagate(opts)
    # ensure the panel device center was updated (within reasonable range)
    cf = mw.sdr_panel.sdr.get_center_frequency()
    assert cf != 145800000.0
