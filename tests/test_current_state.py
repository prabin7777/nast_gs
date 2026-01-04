from datetime import datetime
from pathlib import Path
from nast_gs.prop.propagator import load_tle, current_state


def test_current_state_has_fields():
    here = Path(__file__).resolve().parents[1]
    tle_path = here / "data" / "iss.tle"
    tle = load_tle(str(tle_path))
    st = current_state(tle, datetime.utcnow(), gs_lat=0.0, gs_lon=0.0)
    assert "azdeg" in st and "eldeg" in st and "range_km" in st and "range_rate_km_s" in st
