"""Always-on detection worker: frames -> YOLO -> rules -> Supabase.

Runs in one background thread, sampling the shared CameraService:
  PERSON_DETECTED     -> annotated screenshot + incident row (cooldown-gated)
  SUSPICIOUS_ACTIVITY -> screenshot + 10s clip + incident row (full evidence)

Never raises into the caller; every stage is failure-tolerant so the
camera/API keep serving even if detection or Supabase goes down.
"""
import threading
import time
from typing import Any, Optional

from backend.config import settings


class PipelineWorker:
    def __init__(self, camera: Any,
                 sample_fps: Optional[float] = None,
                 save_person: Optional[bool] = None,
                 person_cooldown_sec: Optional[int] = None) -> None:
        self._cam = camera
        self._fps = sample_fps or settings.pipeline_sample_fps or 1.0
        self._save_person = settings.save_person_detected if save_person is None else save_person
        self._cooldown = person_cooldown_sec or settings.person_cooldown_sec or 120
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._running = False
        self._last_person_save = 0.0
        self._processed = 0
        self._person_saved = 0
        self._suspicious_saved = 0
        self._errors = 0

    def start(self) -> None:
        if self._running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="pipeline",
                                        daemon=True)
        self._running = True
        self._thread.start()

    def stop(self, join_sec: float = 10.0) -> None:
        self._stop.set()
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=join_sec)

    @property
    def status(self) -> dict[str, Any]:
        return {"running": self._running, "sampleFps": self._fps,
                "framesProcessed": self._processed,
                "personSaved": self._person_saved,
                "suspiciousSaved": self._suspicious_saved,
                "errors": self._errors,
                "savePerson": self._save_person,
                "thresholdSec": settings.suspicious_duration_seconds}

    # ---- internals ----
    def _loop(self) -> None:
        try:
            from backend.detection.detector import PersonDetector
            from backend.evidence.capture import EvidenceCapture, RollingBuffer
            from backend.rules.suspicious import RuleEngine
            detector = PersonDetector()
            detector._load()  # noqa: SLF001
            engine = RuleEngine(float(settings.suspicious_duration_seconds))
            buf = RollingBuffer()
            capture = EvidenceCapture()
        except Exception:
            return  # detector unavailable: worker stays down, camera unaffected
        period = 1.0 / max(self._fps, 0.1)
        while not self._stop.is_set():
            t0 = time.time()
            try:
                frame = self._cam.get_frame()
                if frame is not None:
                    buf.push(frame)
                    h, w = frame.shape[:2]
                    dets = detector.detect(frame)
                    for ev in engine.update(dets, (w, h)):
                        self._handle(ev, frame, dets, buf, capture)
                    self._processed += 1
            except Exception:  # noqa: BLE001 — stay alive, count it
                self._errors += 1
            dt = time.time() - t0
            if dt < period:
                self._stop.wait(period - dt)

    def _handle(self, ev: Any, frame: Any, dets: list,
                buf: Any, capture: Any) -> None:
        try:
            if ev.event_type == "PERSON_DETECTED":
                if not self._save_person:
                    return
                now = time.time()
                if now - self._last_person_save < self._cooldown:
                    return
                self._last_person_save = now
                from backend.storage.publish import publish_incident
                try:
                    # Fast path: short clip (~3s before + ~3s after) + shot.
                    res = capture.capture(ev, frame, dets,
                                          self._cam.get_frame, buf,
                                          pre_sec=3.0, total_sec=6.0)
                    publish_incident(
                        res["incidentId"], res["dir"],
                        {"event_type": "PERSON_DETECTED",
                         "confidence": ev.confidence,
                         "description": "Person detected in monitored area"},
                        delete_local=True)
                except Exception:
                    # Fallback: screenshot-only row, evidence preserved.
                    from backend.storage.publish import publish_screenshot_incident
                    iid = capture.incident_id(ev.timestamp)
                    shot_dir = capture.save_screenshot(iid, frame, dets)
                    publish_screenshot_incident(
                        iid, shot_dir,
                        {"event_type": "PERSON_DETECTED",
                         "confidence": ev.confidence,
                         "description": "Person detected in monitored area"},
                        delete_local=True)
                self._person_saved += 1
            elif ev.event_type == "SUSPICIOUS_ACTIVITY":
                from backend.storage.publish import publish_incident
                res = capture.capture(ev, frame, dets,
                                      self._cam.get_frame, buf)
                publish_incident(
                    res["incidentId"], res["dir"],
                    {"event_type": "SUSPICIOUS_ACTIVITY",
                     "confidence": ev.confidence,
                     "description": ev.description,
                     "ai_analysis": self._ai_analysis(res["screenshot"])},
                    delete_local=True)
                self._suspicious_saved += 1
        except Exception:  # noqa: BLE001 — evidence kept locally, counted
            self._errors += 1

    @staticmethod
    def _ai_analysis(screenshot_path: str) -> str:
        """Optional Nemotron description of the incident frame. Empty when
        unconfigured or on any failure — the incident saves regardless."""
        import os
        if not os.getenv("NVIDIA_API_KEY", ""):
            return ""
        try:
            import cv2
            from backend.ai.nemotron import analyze_image
            img = cv2.imread(screenshot_path)
            if img is None:
                return ""
            h, w = img.shape[:2]
            if w > 768:
                img = cv2.resize(img, (768, int(h * 768 / w)))
            ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ok:
                return ""
            res = analyze_image(jpg.tobytes())
            return res["text"] if res.get("ok") else ""
        except Exception:  # noqa: BLE001
            return ""
