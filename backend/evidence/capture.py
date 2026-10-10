"""Stage 5 — evidence capture (local filesystem; Supabase upload is Stage 6).

On a SUSPICIOUS_ACTIVITY trigger:
  screenshot.jpg — latest full-res frame, annotated with person boxes.
  clip.mp4       — 10s clip: ~4s pre-event context (rolling buffer) +
                   ~6s post-trigger, 640px wide @ 10fps.
  event.json     — trigger metadata (reused for the Supabase incident row later).

Layout mirrors the future Storage paths: evidence/{incidentId}/...

Memory is bounded: the buffer keeps small (320px) frames at <=5fps for a
few seconds. The service / detector / rules modules are untouched — the
pipeline feeds frames in via push().
"""
import json
import os
import time
from collections import deque
from typing import Any, Callable, Optional

import cv2
import numpy as np

from backend.detection.detector import Detection, draw_boxes
from backend.rules.suspicious import Event

CLIP_FPS = 10
CLIP_W = 640
PRE_SEC = 4.0
TOTAL_SEC = 10.0
BUFFER_SEC = 6.0
BUFFER_FPS = 5.0


def _small(frame: np.ndarray, width: int = 320) -> np.ndarray:
    h, w = frame.shape[:2]
    if w <= width:
        return frame.copy()
    return cv2.resize(frame, (width, int(h * width / w)))


def _clip_size(frame: np.ndarray) -> tuple[int, int]:
    h, w = frame.shape[:2]
    return (CLIP_W, int(h * CLIP_W / w)) if w != CLIP_W else (w, h)


class RollingBuffer:
    """Keeps the last BUFFER_SEC seconds of small frames with timestamps."""

    def __init__(self, window_sec: float = BUFFER_SEC,
                 max_fps: float = BUFFER_FPS) -> None:
        self._buf: deque[tuple[float, np.ndarray]] = deque()
        self._window = window_sec
        self._min_gap = 1.0 / max_fps
        self._last_push = 0.0

    def push(self, frame: Optional[np.ndarray], now: Optional[float] = None) -> None:
        if frame is None:
            return
        now = time.time() if now is None else now
        if now - self._last_push < self._min_gap:
            return
        self._last_push = now
        self._buf.append((now, _small(frame)))
        while self._buf and now - self._buf[0][0] > self._window:
            self._buf.popleft()

    def __len__(self) -> int:
        return len(self._buf)

    def resample(self, end: float, seconds: float, fps: int,
                 size: tuple[int, int]) -> list[np.ndarray]:
        """Nearest-neighbour resample of [end-seconds, end] to fixed fps/size."""
        if not self._buf:
            return []
        frames = list(self._buf)
        out: list[np.ndarray] = []
        n = int(seconds * fps)
        for i in range(n):
            t = end - seconds + (i + 0.5) / fps
            best = min(frames, key=lambda tf: abs(tf[0] - t))
            out.append(cv2.resize(best[1], size))
        return out


class EvidenceCapture:
    def __init__(self, base_dir: str = "evidence") -> None:
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    @staticmethod
    def incident_id(now: Optional[float] = None) -> str:
        return time.strftime("evt_%Y%m%d_%H%M%S", time.localtime(now))

    def save_screenshot(self, incident_id: str, frame: np.ndarray,
                        detections: list[Detection]) -> str:
        """Annotate + save screenshot.jpg for screenshot-only incidents
        (brief person sightings). Returns the incident dir."""
        d = os.path.join(self.base_dir, incident_id)
        os.makedirs(d, exist_ok=True)
        cv2.imwrite(os.path.join(d, "screenshot.jpg"),
                    draw_boxes(frame, detections),
                    [cv2.IMWRITE_JPEG_QUALITY, 85])
        return d

    def capture(self, event: Event, frame: np.ndarray,
                detections: list[Detection],
                get_frame: Callable[[], Optional[np.ndarray]],
                buffer: RollingBuffer,
                pre_sec: float = PRE_SEC,
                total_sec: float = TOTAL_SEC) -> dict[str, Any]:
        """Blocking: saves screenshot immediately, then records post-trigger
        frames until the clip reaches total_sec. Returns paths + clip stats."""
        iid = self.incident_id(event.timestamp)
        d = os.path.join(self.base_dir, iid)
        os.makedirs(d, exist_ok=True)

        shot_path = os.path.join(d, "screenshot.jpg")
        cv2.imwrite(shot_path, draw_boxes(frame, detections),
                    [cv2.IMWRITE_JPEG_QUALITY, 85])

        size = _clip_size(frame)
        post_sec = total_sec - pre_sec
        t_trigger = time.time()
        pre = buffer.resample(t_trigger, pre_sec, CLIP_FPS, size)
        post: list[np.ndarray] = []
        deadline = t_trigger + post_sec
        while time.time() < deadline:
            f = get_frame()
            if f is not None:
                post.append(cv2.resize(_small(f, 640), size))
            time.sleep(1.0 / CLIP_FPS)
        # Pad shortfalls (slow source) so the clip is always ~total_sec.
        frames = pre + post
        need = int(total_sec * CLIP_FPS)
        if frames:
            while len(frames) < need:
                frames.append(frames[-1])
        clip_path = os.path.join(d, "clip.mp4")
        vw = cv2.VideoWriter(clip_path, cv2.VideoWriter_fourcc(*"mp4v"),
                             CLIP_FPS, size)
        for f in frames[:need]:
            vw.write(f)
        vw.release()

        meta = {"incidentId": iid, "event": event.as_dict(),
                "preFrames": len(pre), "postFrames": len(post)}
        with open(os.path.join(d, "event.json"), "w") as fh:
            json.dump(meta, fh, indent=1)
        return {"incidentId": iid, "dir": d, "screenshot": shot_path,
                "clip": clip_path, "preFrames": len(pre),
                "postFrames": len(post)}
