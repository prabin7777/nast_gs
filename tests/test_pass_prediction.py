from datetime import datetime
from nast_gs.prop.propagator import compute_passes, load_tle
from pathlib import Path


def test_compute_passes_returns_list():
    here = Path(__file__).resolve().parents[1]
    tle_path = here / "data" / "iss.tle"
    tle = load_tle(str(tle_path))
    now = datetime.utcnow()
    passes = compute_passes(tle, now, hours=1, gs_lat=0.0, gs_lon=0.0)
    # result is a list (may be empty depending on satellite and time)
    assert isinstance(passes, list)
    for p in passes:
        assert 'aos' in p and 'los' in p and 'tca' in p and 'max_el_deg' in p