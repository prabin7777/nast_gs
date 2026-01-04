"""Simple NTP time fetch utility (does not set system time)."""
from datetime import datetime, timezone


def get_ntp_time(server: str = "pool.ntp.org") -> datetime:
    try:
        import ntplib
    except Exception as e:
        raise RuntimeError("ntplib is not installed; install with `pip install ntplib`") from e
    c = ntplib.NTPClient()
    resp = c.request(server, version=3)
    return datetime.fromtimestamp(resp.tx_time, tz=timezone.utc)
