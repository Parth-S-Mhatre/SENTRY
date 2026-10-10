"""Stage 2 — continuous stream test. Run from project root:
    python -m backend.test_stream
or:
    python backend/test_stream.py   (or: python test_stream.py)

Runs the CameraService for ~10s, counts decoded frames, computes
approx FPS, saves a sample frame to test_output/test_stream_frame.jpg.

Exit code 0 = PASS, 1 = FAIL. Never prints secrets.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2

from backend.camera.service import CameraService
from backend.config import mask_rtsp_url, settings

RUN_SECONDS = 10
SAVE_PATH = os.path.join("test_output", "test_stream_frame.jpg")
MIN_FRAMES = 10  # lenient MVP bar: avg >= 1 fps over the window


def main() -> int:
    url = settings.rtsp_url_effective.strip()
    print("--------------------------------")
    print("STREAM TEST (~10s)")
    print("--------------------------------")
    print(f"Camera: {settings.camera_name} ({settings.camera_id})")
    print(f"RTSP URL: {mask_rtsp_url(url)}")
    if not url:
        print("Overall result: FAIL")
        print("ERROR: no RTSP URL — set TAPO_USERNAME/TAPO_PASSWORD/TAPO_IP in .env")
        return 1

    svc = CameraService(url, timeout_sec=settings.rtsp_timeout_seconds)
    try:
        svc.start()
    except ValueError as exc:
        print(f"Overall result: FAIL\nERROR: {exc}")
        return 1

    t0 = time.time()
    try:
        time.sleep(RUN_SECONDS)
    except KeyboardInterrupt:
        print("(interrupted — reporting partial results)")
    elapsed = time.time() - t0
    status = svc.get_status()
    frame = svc.get_frame()
    svc.stop()

    frames = status["framesDecoded"]
    fps = round(frames / elapsed, 1) if elapsed > 0 else 0.0
    saved = False
    if frame is not None:
        os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
        saved = bool(cv2.imwrite(SAVE_PATH, frame))

    print(f"Elapsed: {elapsed:.1f}s")
    print(f"Frames decoded: {frames}")
    print(f"Approx FPS: {fps}")
    print(f"Resolution: {status['resolution']}")
    print(f"Connected at end: {status['connected']}")
    print(f"Errors: {status['errors']} | Reconnects: {status['reconnects']}")
    if status.get("lastError"):
        print(f"Last error: {status['lastError']}")
    print(f"Sample frame saved: {'PASS' if saved else 'FAIL'} ({SAVE_PATH})")
    print()

    ok = frames >= MIN_FRAMES and saved
    print(f"Overall result: {'PASS' if ok else 'FAIL'}")
    if not ok:
        if frames < MIN_FRAMES:
            print(f"ERROR: only {frames} frames in {elapsed:.0f}s "
                  f"(need >= {MIN_FRAMES}) — network/auth/stream path?")
        if not saved:
            print("ERROR: could not save sample frame (no frame in memory?)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
