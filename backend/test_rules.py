"""Stage 4 — rules test. Run from project root:
    python -m backend.test_rules

Part 1 (deterministic, simulated 1-fps detection timeline — no camera,
no sleeps, reproducible every run):
  A. 12s continuous presence, threshold 10s -> PERSON_DETECTED at t=0,
     exactly one SUSPICIOUS_ACTIVITY at t>=10.
  B. 3s presence -> PERSON_DETECTED only, no SUSPICIOUS_ACTIVITY.
  C. 6s present, 5s absent (reset), 6s present -> no SUSPICIOUS_ACTIVITY.
  D. Person outside configured area -> ignored entirely.
Part 2 (live wiring, ~10s): real CameraService + PersonDetector frames
flow through RuleEngine without crashing (expects no events, empty scene).

Exit code 0 = all PASS, 1 = any FAIL. Never prints secrets.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.camera.service import CameraService
from backend.config import mask_rtsp_url, settings
from backend.detection.detector import Detection, PersonDetector
from backend.rules.suspicious import RuleEngine

THRESHOLD = 10.0


def person(conf: float = 0.8,
           bbox: tuple[int, int, int, int] = (100, 100, 300, 600)) -> Detection:
    return Detection(confidence=conf, bbox=bbox)


def run_timeline(engine: RuleEngine, timeline: list[list[Detection]],
                 frame_size=(640, 480)) -> list:
    events = []
    for t, dets in enumerate(timeline):
        for e in engine.update(dets, frame_size, now=float(t)):
            events.append((t, e))
    return events


def check(name: str, cond: bool, detail: str = "") -> bool:
    print(f"  [{name}] {'PASS' if cond else 'FAIL'} {detail}")
    return cond


def main() -> int:
    print("--------------------------------")
    print("RULES TEST")
    print("--------------------------------")
    ok = True

    # A: sustained presence fires once.
    eng = RuleEngine(THRESHOLD)
    ev = run_timeline(eng, [[person(0.8)] for _ in range(12)])
    types = [e.event_type for _, e in ev]
    ok &= check("A-rising-edge", types[0] == "PERSON_DETECTED" and ev[0][0] == 0,
                f"first event {types[0]} at t={ev[0][0]}")
    sus = [(t, e) for t, e in ev if e.event_type == "SUSPICIOUS_ACTIVITY"]
    ok &= check("A-fires-once", len(sus) == 1 and sus[0][0] == 10,
                f"fired at t={sus[0][0] if sus else '-'}")
    ok &= check("A-description", "10s" in sus[0][1].description and "threshold 10s" in sus[0][1].description,
                f"'{sus[0][1].description}'")

    # B: brief presence -> no suspicious.
    eng = RuleEngine(THRESHOLD)
    ev = run_timeline(eng, [[person()]] * 3 + [[]] * 3)
    ok &= check("B-brief", [e.event_type for _, e in ev] == ["PERSON_DETECTED"],
                f"events={[e.event_type for _, e in ev]}")

    # C: absence resets the timer.
    eng = RuleEngine(THRESHOLD)
    ev = run_timeline(eng, [[person()]] * 6 + [[]] * 5 + [[person()]] * 6)
    ok &= check("C-reset", all(e.event_type != "SUSPICIOUS_ACTIVITY" for _, e in ev),
                f"events={[e.event_type for _, e in ev]}")

    # D: person outside configured left-half area is ignored.
    eng = RuleEngine(THRESHOLD, area=(0.0, 0.0, 0.5, 1.0))
    right = (400, 100, 600, 400)  # center x=500/640 -> right half
    ev = run_timeline(eng, [[person(bbox=right)]] * 12)
    ok &= check("D-area-filter", ev == [], f"events={len(ev)} (want 0)")

    # Part 2: live wiring smoke test.
    print("Live wiring (~10s)...")
    url = settings.rtsp_url_effective.strip()
    print(f"RTSP URL: {mask_rtsp_url(url)}")
    if not url:
        print("Live wiring: FAIL (no RTSP URL in .env)")
        return 1
    svc = CameraService(url, timeout_sec=settings.rtsp_timeout_seconds)
    det = PersonDetector()
    eng = RuleEngine(float(settings.suspicious_duration_seconds
                           if hasattr(settings, "suspicious_duration_seconds") else 10))
    live_events = 0
    try:
        det._load()  # noqa: SLF001
        svc.start()
        t_end = time.time() + 10
        frames = 0
        while time.time() < t_end:
            f = svc.get_frame()
            if f is None:
                time.sleep(0.3)
                continue
            frames += 1
            h, w = f.shape[:2]
            live_events += len(eng.update(det.detect(f), (w, h)))
            time.sleep(1.0)
        print(f"  frames sampled: {frames}, engine events: {live_events}")
        ok &= check("live-no-crash", frames > 0, "")
    except Exception as exc:  # noqa: BLE001
        ok &= check("live-no-crash", False, f"{exc}")
    finally:
        svc.stop()

    print(f"\nOverall result: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
