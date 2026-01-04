# NAST Geo Suite (satellite tracker)

NAST Geo Suite is a cross-platform desktop application for tracking satellites using TLE data and SDR hardware (RTL-SDR, USRP B210). It includes orbit propagation, Doppler correction, CW/FM demodulation, audio output and an azimuth/elevation pipeline for rotor control.

This repository contains an initial scaffold and a minimal demo that:
- Imports a TLE
- Propagates satellite positions using Skyfield
- Shows a simple groundtrack on a Leaflet map embedded in a PyQt WebEngine view

Planned modules: `prop` (propagation), `sdr` (SDR drivers), `demod` (demodulation/audio), `gui` (visualization), `rotor` (rotor control).

See `requirements.txt` for libraries.

Usage (demo):
```
python -m scripts.run_demo
```

License: MIT
