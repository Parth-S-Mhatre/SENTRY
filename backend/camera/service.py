"""Stage 2 — continuous RTSP frame reader.

One background thread per camera: opens the RTSP stream (TCP), reads
frames in a loop, and keeps only the latest frame in memory. On any
failure it releases the capture, waits with backoff, and reconnects
until stopped. Nothing here does detection, recording, or uploads —
later stages consume get_frame() / get_status().
"""
import threading
import time
from typing import Any, Optional

import cv2
import numpy as np

from backend.camera.rtsp import open_stream


class CameraService:
    def __init__(self, url: str, timeout_sec: int = 10,
                 reconnect_delay_sec: float = 3.0,
                 max_backoff_sec: float = 30.0) -> None:
        self._url = url
        self._timeout = timeout_sec
        self._base_delay = reconnect_delay_sec
        self._max_backoff = max_backoff_sec

        self._lock = threading.Lock()
        self._latest: Optional[np.ndarray] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

        self._running = False
        self._connected = False
        self._frames = 0
        self._errors = 0
        self._reconnects = 0
        self._width = 0
        self._height = 0
        self._start_time: float = 0.0
        self._last_frame_time: float = 0.0
        self._last_error: str = ""

    # ---- lifecycle ----
    def start(self) -> None:
        if self._running:
            return
        if not self._url:
            raise ValueError("no RTSP URL configured — set Tapo credentials in .env")
        self._stop.clear()
        self._start_time = time.time()
        self._thread = threading.Thread(target=self._loop, name="camera-rtsp",
                                        daemon=True)
        self._running = True
        self._thread.start()

    def stop(self, join_sec: float = 5.0) -> None:
        self._stop.set()
        self._running = False
        self._connected = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=join_sec)

    # ---- consumers (thread-safe) ----
    def get_frame(self) -> Optional[np.ndarray]:
        """Return a copy of the latest frame, or None if none yet."""
        with self._lock:
            return None if self._latest is None else self._latest.copy()

    def get_status(self) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            frames, errs, reconns = self._frames, self._errors, self._reconnects
            w, h = self._width, self._height
            last_age = (now - self._last_frame_time) if self._last_frame_time else -1
            last_err = self._last_error
        elapsed = now - self._start_time if self._start_time else 0.0
        return {
            "running": self._running,
            "connected": self._connected,
            "framesDecoded": frames,
            "fpsApprox": round(frames / elapsed, 1) if elapsed > 0.5 else 0.0,
            "resolution": f"{w}x{h}" if w and h else "unknown",
            "lastFrameAgeSec": round(last_age, 1) if last_age >= 0 else -1,
            "errors": errs,
            "reconnects": reconns,
            "uptimeSec": round(elapsed, 1),
            "lastError": last_err,
        }

    @property
    def is_running(self) -> bool:
        return self._running

    # ---- internals ----
    def _store(self, frame: "np.ndarray") -> None:
        with self._lock:
            self._latest = frame.copy()
            h, w = frame.shape[:2]
            self._width, self._height = w, h
            self._frames += 1
            self._last_frame_time = time.time()

    def _note_error(self, msg: str) -> None:
        with self._lock:
            self._errors += 1
            self._last_error = msg[:200]

    def _loop(self) -> None:
        backoff = self._base_delay
        while not self._stop.is_set():
            cap = None
            try:
                cap = open_stream(self._url, self._timeout)
                if not cap.isOpened():
                    self._note_error("open failed (unreachable/auth/stream path?)")
                    self._connected = False
                else:
                    self._connected = True
                    with self._lock:
                        self._reconnects += 1 if self._frames or self._errors else 0
                    backoff = self._base_delay  # reset on successful open
                    while not self._stop.is_set():
                        ok, frame = cap.read()
                        if not ok or frame is None:
                            self._note_error("frame read failed (network/codec?)")
                            self._connected = False
                            break
                        self._connected = True
                        self._store(frame)
            except Exception as exc:  # noqa: BLE001 — stay alive, report
                self._note_error(f"reader exception: {exc}")
                self._connected = False
            finally:
                try:
                    if cap is not None:
                        cap.release()
                except Exception:
                    pass
            if not self._stop.is_set():
                # Wait (interruptible) before reconnecting.
                self._stop.wait(min(backoff, self._max_backoff))
                backoff = min(backoff * 2, self._max_backoff)
        self._connected = False
