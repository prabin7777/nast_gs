"""RTTY demodulator stub (Baudot) - placeholder implementation.

This module provides a minimal API for the GUI to call; a full RTTY decoder
will be implemented later. For now, rtty_demod returns a dict with a 'text'
field (empty) and an informative 'status'.
"""
from typing import Dict


def rtty_demod(iq) -> Dict:
    """Placeholder RTTY demodulator. Returns a dict with keys: text, status."""
    return {"text": "", "status": "not-implemented"}
