"""Streaming thread that reads IQ from SDR devices and publishes samples for processing."""
import threading
import time
import numpy as np
import queue


class SDRStreamer(threading.Thread):
    def __init__(self, sdr_device, sample_rate: float = 2.4e6, block_size: int = 16384):
        super().__init__(daemon=True)
        self.sdr = sdr_device
        self.sample_rate = sample_rate
        self.block_size = block_size
        self._stop_evt = threading.Event()
        self.out_q = queue.Queue(maxsize=10)

    def run(self):
        try:
            self.sdr.start()
        except Exception:
            pass

        while not self._stop_evt.is_set():
            try:
                samples = self.sdr.read_samples(self.block_size)
                self.out_q.put(samples, timeout=1.0)
            except Exception:
                time.sleep(0.1)

    def stop(self):
        self._stop_evt.set()
        try:
            self.sdr.stop()
        except Exception:
            pass
