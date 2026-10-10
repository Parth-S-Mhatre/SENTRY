"""Stage 5 — evidence test. Run from project root:
    python -m backend.test_evidence

Warms a RollingBuffer with ~7s of LIVE frames, fires a trigger on the
live frame, captures screenshot + 10s clip, then verifies: files exist,
sizes sane, clip opens and plays back at ~10s / 10fps / 640px wide with
pre-trigger context frames included.

Trigger honesty: if the live detector sees a person, the trigger uses
the real RuleEngine event; otherwise a clearly-labeled SIMULATED
SUSPICIOUS_ACTIVITY on the live frame exercises the same capture path
(the scene is usually empty foliage — detection logic was proven in
Stages 3–4).

Exit code 0 = PASS, 1 = FAIL. Never prints secrets.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2

from backend.camera.service import CameraService
from backend.config import mask_rtsp_url, settings
from backend.detection.detector import PersonDetector
from backend.evidence.capture import EvidenceCapture, RollingBuffer
from backend.rules.suspicious import Event


def check(name: str, cond: bool, detail: str = "") -> bool:
    print(f"  [{name}] {'PASS' if cond else 'FAIL'} {detail}")
    return cond


def main() -> int:
    url = settings.rtsp_url_effective.strip()
    print("--------------------------------")
    print("EVIDENCE TEST")
    print("--------------------------------")
    print(f"RTSP URL: {mask_rtsp_url(url)}")
    if not url:
        print("Overall result: FAIL\nERROR: no RTSP URL in .env")
        return 1
    ok = True

    svc = CameraService(url, timeout_sec=settings.rtsp_timeout_seconds)
    det = PersonDetector()
    buf = RollingBuffer()
    cap = EvidenceCapture()
    try:
        det._load()  # noqa: SLF001
        svc.start()
        print("Warming rolling buffer (~7s of live frames)...")
        t_end = time.time() + 7
        while time.time() < t_end:
            buf.push(svc.get_frame())
            time.sleep(0.2)
        ok &= check("buffer-warm", len(buf) >= 10, f"{len(buf)} frames buffered")

        frame = svc.get_frame()
        if frame is None:
            print("Overall result: FAIL\nERROR: no live frame available")
            return 1
        h, w = frame.shape[:2]
        dets = det.detect(frame)
        if dets:
            ev = Event("SUSPICIOUS_ACTIVITY", time.time(),
                       max(d.confidence for d in dets),
                       "Potential suspicious activity: person continuously present "
                       f"(threshold {settings.suspicious_duration_seconds:.0f}s)",
                       duration_sec=float(settings.suspicious_duration_seconds))
            print(f"Trigger: REAL engine-style event ({len(dets)} person(s))")
        else:
            ev = Event("SUSPICIOUS_ACTIVITY", time.time(), 0.57,
                       "SIMULATED trigger on live frame (empty scene) to test "
                       "capture path; detection proven in Stages 3-4",
                       duration_sec=float(settings.suspicious_duration_seconds))
            print("Trigger: SIMULATED (no person in live scene)")

        print("Capturing (screenshot now + ~6s post-trigger video)...")
        res = cap.capture(ev, frame, dets, svc.get_frame, buf)
        print(f"Incident: {res['incidentId']} pre={res['preFrames']} post={res['postFrames']}")
        ok &= check("pre-context", res["preFrames"] >= 30,
                    f"{res['preFrames']} pre-trigger frames in clip")

        shot = res["screenshot"]
        ok &= check("screenshot-exists", os.path.exists(shot), shot)
        ok &= check("screenshot-size", os.path.exists(shot) and os.path.getsize(shot) > 5000,
                    f"{os.path.getsize(shot) if os.path.exists(shot) else 0} bytes")
        img = cv2.imread(shot)
        ok &= check("screenshot-readable", img is not None and img.shape[0] > 0,
                    f"{img.shape if img is not None else None}")

        clip = res["clip"]
        ok &= check("clip-exists", os.path.exists(clip), clip)
        ok &= check("clip-size", os.path.exists(clip) and os.path.getsize(clip) > 50000,
                    f"{os.path.getsize(clip) if os.path.exists(clip) else 0} bytes")
        vc = cv2.VideoCapture(clip)
        n = int(vc.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = vc.get(cv2.CAP_PROP_FPS) or 0
        cw = int(vc.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        chh = int(vc.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        vrearzt, _ = vc.read()
        vc.release()
        dur = n / fps if fps else 0
        ok &= check("clip-playable", n > 0 and vrearzt,
                    f"{n} frames @ {fps:.0f}fps = {dur:.1f}s, {cw}x{chh}")
        ok &= check("clip-duration", 9.0 <= dur <= 11.0, f"{dur:.1f}s (want ~10s)")
        ok &= check("clip-size-640", cw == 640, f"{cw}x{chh}")
    finally:
        svc.stop()

    print(f"\nOverall result: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
