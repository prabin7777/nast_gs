"""Run a minimal demo: load a sample TLE, compute groundtrack and show on map."""
from datetime import datetime
import sys
from pathlib import Path

from nast_gs.prop import load_tle, propagate_tle
from nast_gs.gui import MapWindow
from PyQt6 import QtWidgets


def main():
    here = Path(__file__).resolve().parents[1]
    tle_path = here / "data" / "iss.tle"
    tle = load_tle(str(tle_path))

    start = datetime.utcnow()
    # propagate 90 minutes in 60s steps
    points = propagate_tle(tle, start, minutes=90, step_s=60, gs_lat=25.0, gs_lon= -80.0, gs_alt_m=5.0)

    latlon = [(p["sublat"], p["sublon"]) for p in points]

    app = QtWidgets.QApplication(sys.argv)
    win = MapWindow()
    win.set_track(latlon)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
