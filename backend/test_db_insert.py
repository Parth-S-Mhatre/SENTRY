"""Stage 6C — Supabase database insertion test. Run from project root:
    python -m backend.test_db_insert

Inserts ONE clearly-marked TEST row into `incidents`, reads it back by
id, and verifies every field. No pipeline changes, no file changes.

Exit 0 = PASS, 1 = FAIL. The service key is never printed.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import settings

ROW = {
    "camera_id": "camera_01",
    "camera_name": "Entrance Camera",
    "event_type": "SUSPICIOUS_ACTIVITY",
    "confidence": 0.87,
    "description": "TEST INCIDENT — Supabase database connectivity check",
    "status": "NEW",
    "screenshot_path": "test/connection-test/screenshot.jpg",
    "clip_path": None,
}


def _scrub(text: str) -> str:
    key = settings.supabase_service_key
    if key and len(key) > 8:
        text = text.replace(key, "***")
    return re.sub(r"eyJ[A-Za-z0-9_-]{10,}[A-Za-z0-9_.\-]*", "***", text)


def main() -> int:
    print("--------------------------------")
    print("DATABASE INSERT TEST")
    print("--------------------------------")
    try:
        from backend.storage.supabase_client import get_client
        client = get_client()
        ins = client.table("incidents").insert(ROW).execute()
        rows = ins.data or []
        assert len(rows) == 1, f"expected 1 inserted row, got {len(rows)}"
        rid = rows[0].get("id")
        print(f"Insert: PASS (id={rid})")
    except Exception as exc:  # noqa: BLE001
        print(f"Overall result: FAIL\nERROR: {_scrub(str(exc))}")
        return 1

    try:
        got = client.table("incidents").select("*").eq("id", rid).execute().data
        assert got and len(got) == 1, "row not readable after insert"
        back = got[0]
        mism = [k for k, v in ROW.items() if back.get(k) != v]
        print(f"Read-back: id={back.get('id')} created_at={back.get('created_at')}")
        if mism:
            print(f"Overall result: FAIL\nERROR: field mismatch: {mism}")
            return 1
        print(f"Field check: PASS (all {len(ROW)} fields match)")
    except AssertionError as exc:
        print(f"Overall result: FAIL\nERROR: {_scrub(str(exc))}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Overall result: FAIL\nERROR: {_scrub(str(exc))}")
        return 1

    print("\nOverall result: PASS")
    print(f"NOTE: TEST row id={rid} left in `incidents` — delete it in Supabase when done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
