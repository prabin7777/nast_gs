import subprocess
import shutil
import socket
import time


def is_port_open(host: str, port: int, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def launch_gqrx() -> subprocess.Popen:
    exe = shutil.which("gqrx")
    if not exe:
        raise RuntimeError("gqrx not found in PATH. Install Gqrx or add it to PATH.")
    # No CLI option guaranteed for enabling remote control.
    # This just launches Gqrx.
    return subprocess.Popen([exe])


def ensure_gqrx_running(host="127.0.0.1", port=7356, wait_s: float = 6.0) -> bool:
    if is_port_open(host, port):
        return True
    try:
        launch_gqrx()
    except Exception:
        return False

    t0 = time.time()
    while time.time() - t0 < wait_s:
        if is_port_open(host, port):
            return True
        time.sleep(0.2)
    return False
