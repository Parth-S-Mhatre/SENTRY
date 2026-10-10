"""Stage 3 — live person-detection test. Run from project root:
    python -m backend.test_detection

Pulls frames from the live CameraService for ~60s, runs the pretrained
person detector (~1 fps sampling), prints per-sample results, and saves
the best annotated frame to test_output/test_detection_frame.jpg.

PASS = a person was actually detected in the live stream.
FAIL = no person seen (stand in front of the camera and re-run).

Exit code 0 = PASS, 1 = FAIL. Never prints secrets.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2

from backend.camera.service import CameraService
from backend.config import mask_rtsp_url, settings
from backend.detection.detector import PersonDetector, draw_boxes

RUN_SECONDS = 60
SAMPLE_EVERY_SEC = 1.0
SAVE_PATH = os.path.join("test_output", "test_detection_frame.jpg")


def main() -> int:
    url = settings.rtsp_url_effective.strip()
    print("--------------------------------")
    print("PERSON DETECTION TEST (~60s)")
    print("--------------------------------")
    print(f"Camera: {settings.camera_name} ({settings.camera_id})")
    print(f"RTSP URL: {mask_rtsp_url(url)}")
    print("Tip: stand / walk in front of the camera during this test.")
    if not url:
        print("Overall result: FAIL\nERROR: no RTSP URL — set Tapo credentials in .env")
        return 1

    try:
        detector = PersonDetector()
        # Warm up (downloads yolov8n.pt on first ever run).
        print("Loading model...", flush=True)
        detector._load()
        print("Model ready.")
    except Exception as exc:  # noqa: BLE001, SLF001
        print(f"Overall result: FAIL\nERROR: model load failed: {exc}")
        return 1

    svc = CameraService(url, timeout_sec=settings.rtsp_timeout_seconds)
    try:
        svc.start()
    except ValueError as exc:
        print(f"Overall result: FAIL\nERROR: {exc}")
        return 1

    best: list = []
    best_frame = None
    samples = 0
    t_end = time.time() + RUN_SECONDS
    try:
        while time.time() < t_end:
            frame = svc.get_frame()
            if frame is None:
                time.sleep(0.3)
                continue
            samples += 1
            try:
                dets = detector.detect(frame)
            except Exception as exc:  # noqa: BLE001
                print(f"[sample {samples}] detector error: {exc}")
                break
            tag = ", ".join(f"Person {d.confidence:.2f}" for d in dets) or "no person"
            print(f"[sample {samples}] {tag}")
            if len(dets) > len(best):
                best = dets
                best_frame = frame
            time.sleep(SAMPLE_EVERY_SEC)
    except KeyboardInterrupt:
        print("(interrupted — reporting partial results)")
    finally:
        svc.stop()

    stats = detector.stats
    print(f"\nSamples: {samples} | frames with person: {stats['personFrames']}")
    if best_frame is not None:
        os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
        cv2.imwrite(SAVE_PATH, draw_boxes(best_frame, best))
        top = max(d.confidence for d in best)
        print(f"Best: {len(best)} person(s), top confidence {top:.2f}")
        print(f"Annotated frame: {SAVE_PATH}")

    ok = len(best) > 0
    print(f"\nOverall result: {'PASS' if ok else 'FAIL'}")
    if not ok:
        print("ERROR: no person detected — stand in front of the camera and re-run.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
