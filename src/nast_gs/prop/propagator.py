"""Basic TLE import and propagation using skyfield."""
from skyfield.api import EarthSatellite, load, wgs84
from datetime import datetime, timedelta
from typing import List, Dict


def load_tle(path: str) -> List[str]:
    """Load TLE file containing two-line elements. Returns list [name, line1, line2]."""
    with open(path, "r") as f:
        lines = [l.strip() for l in f if l.strip()]
    if len(lines) >= 3:
        return [lines[0], lines[1], lines[2]]
    raise ValueError("TLE file must contain at least 3 non-empty lines (name, line1, line2)")


def propagate_tle(tle: List[str], start_dt: datetime, minutes: int, step_s: int, gs_lat: float, gs_lon: float, gs_alt_m: float = 0.0) -> List[Dict]:
    """Propagate TLE for a time range and return positions and az/el for a ground station.

    Returns a list of dicts with keys: time (datetime), sublat, sublon, subalt_m, azdeg, eldeg, range_km
    """
    ts = load.timescale()
    name, line1, line2 = tle
    sat = EarthSatellite(line1, line2, name, ts)

    results = []
    steps = int((minutes * 60) / step_s)
    for i in range(steps + 1):
        t = start_dt + timedelta(seconds=i * step_s)
        tt = ts.utc(t.year, t.month, t.day, t.hour, t.minute, t.second + t.microsecond / 1e6)
        geocentric = sat.at(tt)
        subpoint = wgs84.subpoint(geocentric)
        # compute az/el from ground station and also range-rate (radial velocity)
        observer = wgs84.latlon(gs_lat, gs_lon, elevation_m=gs_alt_m)
        observer_at = observer.at(tt)
        topocentric = geocentric - observer_at
        alt, az, distance = topocentric.altaz()

        # position and velocity vectors relative to observer (km, km/s)
        pos = topocentric.position.km
        vel = topocentric.velocity.km_per_s
        # radial velocity (range rate) = (pos . vel) / |pos|
        from math import sqrt

        pos_norm = sqrt(pos[0] ** 2 + pos[1] ** 2 + pos[2] ** 2)
        range_rate_km_s = 0.0
        if pos_norm != 0.0:
            range_rate_km_s = (pos[0] * vel[0] + pos[1] * vel[1] + pos[2] * vel[2]) / pos_norm

        results.append({
            "time": t,
            "sublat": subpoint.latitude.degrees,
            "sublon": subpoint.longitude.degrees,
            "subalt_m": subpoint.elevation.m,
            "azdeg": az.degrees,
            "eldeg": alt.degrees,
            "range_km": distance.km,
            "range_rate_km_s": range_rate_km_s,
        })

    return results


def current_state(tle: List[str], dt: datetime, gs_lat: float, gs_lon: float, gs_alt_m: float = 0.0) -> Dict:
    """Compute instantaneous satellite state relative to a ground station at a given datetime.

    Returns dict with keys: time, sublat, sublon, subalt_m, azdeg, eldeg, range_km, range_rate_km_s
    """
    ts = load.timescale()
    name, line1, line2 = tle
    sat = EarthSatellite(line1, line2, name, ts)
    tt = ts.utc(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second + dt.microsecond / 1e6)
    geocentric = sat.at(tt)
    subpoint = wgs84.subpoint(geocentric)

    observer = wgs84.latlon(gs_lat, gs_lon, elevation_m=gs_alt_m)
    observer_at = observer.at(tt)
    topocentric = geocentric - observer_at
    alt, az, distance = topocentric.altaz()

    pos = topocentric.position.km
    vel = topocentric.velocity.km_per_s
    from math import sqrt

    pos_norm = sqrt(pos[0] ** 2 + pos[1] ** 2 + pos[2] ** 2)
    range_rate_km_s = 0.0
    if pos_norm != 0.0:
        range_rate_km_s = (pos[0] * vel[0] + pos[1] * vel[1] + pos[2] * vel[2]) / pos_norm

    return {
        "time": dt,
        "sublat": subpoint.latitude.degrees,
        "sublon": subpoint.longitude.degrees,
        "subalt_m": subpoint.elevation.m,
        "azdeg": az.degrees,
        "eldeg": alt.degrees,
        "range_km": distance.km,
        "range_rate_km_s": range_rate_km_s,
    }


def compute_passes(tle: List[str], start_dt: datetime, hours: int, gs_lat: float, gs_lon: float, gs_alt_m: float = 0.0, step_s: int = 30):
    """Compute satellite passes over a ground station for the next `hours` hours.

    Returns a list of passes with keys: aos (datetime), los (datetime), tca (datetime), max_el_deg (float), duration_s (int)
    """
    minutes = hours * 60
    pts = propagate_tle(tle, start_dt, minutes=minutes, step_s=step_s, gs_lat=gs_lat, gs_lon=gs_lon, gs_alt_m=gs_alt_m)
    passes = []
    in_pass = False
    current_pass_pts = []
    for p in pts:
        el = p.get('eldeg', 0.0)
        if el > 0.0:
            in_pass = True
            current_pass_pts.append(p)
        else:
            if in_pass:
                # pass ended
                if current_pass_pts:
                    # compute AOS, LOS, TCA and max elevation
                    aos = current_pass_pts[0]['time']
                    los = current_pass_pts[-1]['time']
                    # TCA = time of max elevation
                    max_pt = max(current_pass_pts, key=lambda x: x.get('eldeg', 0.0))
                    tca = max_pt['time']
                    max_el = max_pt.get('eldeg', 0.0)
                    duration_s = int((los - aos).total_seconds())
                    passes.append({
                        'aos': aos,
                        'los': los,
                        'tca': tca,
                        'max_el_deg': max_el,
                        'duration_s': duration_s,
                    })
                current_pass_pts = []
            in_pass = False
    # handle case where pass continues to end of window
    if current_pass_pts:
        aos = current_pass_pts[0]['time']
        los = current_pass_pts[-1]['time']
        max_pt = max(current_pass_pts, key=lambda x: x.get('eldeg', 0.0))
        tca = max_pt['time']
        max_el = max_pt.get('eldeg', 0.0)
        duration_s = int((los - aos).total_seconds())
        passes.append({
            'aos': aos,
            'los': los,
            'tca': tca,
            'max_el_deg': max_el,
            'duration_s': duration_s,
        })

    return passes
