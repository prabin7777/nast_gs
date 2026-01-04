"""Simple config persistence for NAST Geo Suite."""
import json
import os
from typing import Dict

_CONFIG_PATH = os.path.expanduser("~/.nast_gs_config.json")


def load_config() -> Dict:
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(cfg: Dict) -> None:
    d = os.path.dirname(_CONFIG_PATH)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)
    with open(_CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
