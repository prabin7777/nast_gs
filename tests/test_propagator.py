from datetime import datetime
from nast_gs.prop import load_tle, propagate_tle
from pathlib import Path


def test_propagate_returns_points():
    here = Path(__file__).resolve().parents[1]
    tle_path = here / "data" / "iss.tle"
    tle = load_tle(str(tle_path))
    start = datetime.utcnow()
    pts = propagate_tle(tle, start, minutes=10, step_s=60, gs_lat=0.0, gs_lon=0.0)
    assert len(pts) > 0
    p = pts[0]
    assert "sublat" in p and "sublon" in p and "azdeg" in p and "eldeg" in p
