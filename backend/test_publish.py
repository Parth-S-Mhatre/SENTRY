"""Stage 6D — publish integration test. Run from project root:
    python -m backend.test_publish

Runs the REAL Stage 5 flow (live frames -> buffer -> capture), then
publishes: both files to Storage, row to `incidents`, local dir deleted.
Also checks the failure path preserves local files (missing dir raises).

Leaves labeled TEST artifacts in Supabase (folder + row) — delete them
in the dashboard when done. Exit 0 = PASS, 1 = FAIL. Key never printed.
"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.camera.service import CameraService
from backend.config import settings
from backend.detection.detector import PersonDetector
from backend.evidence.capture import EvidenceCapture, RollingBuffer
from backend.rules.suspicious import Event


def _scrub(text: str) -> str:
    key = settings.supabase_service_key
    if key and len(key) > 8:
        text = text.replace(key, "***")
    return re.sub(r"eyJ[A-Za-z0-9_-]{10,}[A-Za-z0-9_.\-]*", "***", text)


def check(name: str, cond: bool, detail: str = "") -> bool:
    print(f"  [{name}] {'PASS' if cond else 'FAIL'} {detail}")
    return cond


def main() -> int:
    print("--------------------------------")
    print("PUBLISH INTEGRATION TEST")
    print("--------------------------------")
    ok = True
    try:
        from backend.storage.publish import publish_incident
        from backend.storage.supabase_client import get_client
    except Exception as exc:  # noqa: BLE001
        print(f"Overall result: FAIL\nERROR: import: {_scrub(str(exc))}")
        return 1

    # Failure path first (no camera needed): missing dir must raise.
    try:
        publish_incident("test_missing", "evidence/does_not_exist", {})
        ok &= check("fail-preserved", False, "should have raised")
    except FileNotFoundError:
        ok &= check("fail-preserved", True, "missing dir raises, nothing deleted")
    except Exception as exc:  # noqa: BLE001
        ok &= check("fail-preserved", False, _scrub(str(exc))[:100])

    url = settings.rtsp_url_effective.strip()
    if not url:
        print("Overall result: FAIL\nERROR: no RTSP URL in .env")
        return 1
    svc = CameraService(url, timeout_sec=settings.rtsp_timeout_seconds)
    det = PersonDetector()
    buf = RollingBuffer()
    cap = EvidenceCapture()
    try:
        det._load()  # noqa: SLF001
        svc.start()
        t_end = time.time() + 7
        while time.time() < t_end:
            buf.push(svc.get_frame())
            time.sleep(0.2)
        frame = svc.get_frame()
        assert frame is not None, "no live frame"
        ev = Event("SUSPICIOUS_ACTIVITY", time.time(), 0.57,
                   "TEST publish — Stage 6D integration check (safe to delete)",
                   duration_sec=10.0)
        res = cap.capture(ev, frame, det.detect(frame), svc.get_frame, buf)
        iid, local_dir = res["incidentId"], res["dir"]
        print(f"Captured: {iid}")
    except Exception as exc:  # noqa: BLE001
        print(f"Overall result: FAIL\nERROR: capture: {_scrub(str(exc))}")
        return 1
    finally:
        svc.stop()

    meta = {"event_type": "SUSPICIOUS_ACTIVITY", "confidence": 0.57,
            "description": "TEST publish — Stage 6D integration check (safe to delete)"}
    try:
        pub = publish_incident(iid, local_dir, meta, delete_local=True)
        print(f"Published: db id={pub['dbId']}")
    except Exception as exc:  # noqa: BLE001
        print(f"Overall result: FAIL\nERROR: publish: {_scrub(str(exc))}")
        print(f"Local evidence preserved at: {local_dir}")
        return 1

    try:
        client = get_client()
        files = client.storage.from_("evidence").list(f"incidents/{iid}")
        names = sorted(f.get("name", "") for f in files)
        ok &= check("storage-files", names == ["clip.mp4", "screenshot.jpg"],
                    f"{names}")
        rows = client.table("incidents").select("*").eq("id", pub["dbId"]).execute().data
        row = rows[0] if rows else {}
        ok &= check("db-row", row.get("screenshot_path") == pub["screenshot_path"] and
                    row.get("clip_path") == pub["clip_path"] and
                    row.get("status") == "NEW",
                    f"screenshot_path={row.get('screenshot_path')}")
        ok &= check("local-deleted", not os.path.exists(local_dir),
                    "local evidence removed after success")
    except Exception as exc:  # noqa: BLE001
        ok &= check("verify", False, _scrub(str(exc))[:150])

    print(f"\nOverall result: {'PASS' if ok else 'FAIL'}")
    if ok:
        print(f"NOTE: TEST artifacts left in Supabase (incidents/{iid}/ + row) — delete when done.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
