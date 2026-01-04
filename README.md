# NAST Geo Suite (Satellite Tracker)

NAST Geo Suite is a cross-platform desktop application for satellite tracking and ground-station operations using Two-Line Element (TLE) data and Software Defined Radio (SDR) hardware.

It is built for research, education, and real ground-station use. The focus is correctness, modular design, and explicit control of the full tracking and RF chain.

---

## Overview

NAST Geo Suite provides an integrated environment for:

- Orbit propagation and pass prediction  
- Real-time Doppler correction  
- SDR reception and demodulation  
- Antenna rotor control (Azimuth / Elevation)  
- Visualization of satellite ground tracks and passes  

The software is designed to scale from a demo environment to an operational ground station.

---

## Features

### Orbit Propagation & Tracking
- Load and parse TLE files
- Orbit propagation using **Skyfield**
- Ground-track visualization on an embedded **Leaflet** map
- Pass prediction with AOS, LOS, TCA, and maximum elevation
- Real-time computation of azimuth, elevation, slant range, and range rate
- NTP-based time synchronization for accurate tracking

### SDR Integration
- RTL-SDR support (tested)
- USRP B210 support (planned / partial)
- Real-time Doppler correction
- Configurable center frequency and sample rate
- IQ recording and demodulated audio recording
- Integrated spectrum view

### Demodulation
- FM demodulation (working)
- CW demodulation (planned)
- Audio playback via system output
- Framework for digital decoders (RTTY, AX.25, etc.)

### Rotor Control
- Azimuth / Elevation control pipeline
- Prosistel protocol support
- Serial port configuration
- Manual test movement and park commands
- Designed for closed-loop real-time tracking

### GUI
- PyQt-based desktop interface
- Embedded web map using Qt WebEngine
- Integrated tracking, SDR, and rotor panels
- Linux primary target (Windows / macOS planned)

---

## Project Structure

```
nast-geo-suite/
├── prop/          # Orbit propagation and pass prediction
├── sdr/           # SDR drivers and Doppler correction
├── demod/         # Demodulation and audio processing
├── rotor/         # Rotor control and protocols
├── gui/           # GUI widgets and visualization
├── scripts/
│   └── run_demo.py
├── requirements.txt
├── README.md
└── LICENSE
```

---

## Requirements

- Python 3.8 or newer
- PyQt5
- PyQt WebEngine
- Skyfield
- NumPy
- SciPy
- pyrtlsdr
- sounddevice
- soundfile
- pyserial

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Usage (Demo)

Run the demo application:

```bash
python -m scripts.run_demo
```

The demo allows you to load a TLE, propagate satellite orbits, view ground tracks, and compute passes. SDR and rotor features are present but not fully automated in the demo.

---

## Configuration Notes

### Ground Station
- Latitude, longitude, and altitude must be set correctly
- NTP synchronization is recommended for accurate Doppler and pointing

### SDR
- RTL-SDR tested with standard dongles
- Sample rates above 2.4 MS/s may be unstable on some systems
- Doppler correction assumes correct system time

### Rotor
- Prosistel protocol implemented
- Serial baud rate and port must match hardware
- Safety limits should be enforced in rotor firmware

---

## Current Status

This project is early-stage but functional.

### Implemented
- TLE parsing and propagation
- Ground-track visualization
- Pass prediction
- RTL-SDR device detection
- Basic FM demodulation
- Rotor communication framework

### In Progress
- Full SDR pipeline stability
- Automated rotor tracking loop
- Advanced demodulators
- Digital protocol decoders
- Error handling and recovery logic

---

## Design Philosophy

- No black-box tracking logic
- Explicit orbital mechanics
- Hardware-agnostic SDR architecture
- Modular subsystems
- Suitable for research-grade ground stations

---

## Roadmap (High Level)

- Stable SDR backend abstraction
- Closed-loop rotor tracking
- CW and digital demodulators
- Recording and playback tools
- SatNOGS interoperability layer
- Reproducible deployment packaging

---

## Contributing

Contributions are welcome if they are technically sound, clearly documented, and aligned with the project structure. Open an issue before submitting major changes.

---

## License

MIT License. You are free to use, modify, and distribute this software with attribution.

