"""Stage 6B — Supabase Storage upload test. Run from project root:
    python -m backend.test_storage_upload

Uploads the latest Stage 5 evidence screenshot (located via glob, never
assumed) to the private `evidence` bucket at
test/connection-test/screenshot.jpg, then verifies by downloading the
bytes back and comparing size. No DB writes, no local deletions.

Exit 0 = PASS, 1 = FAIL. The service key is never printed.
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import settings

DEST = "test/connection-test/screenshot.jpg"
BUCKET = "evidence"


def _scrub(text: str) -> str:
    key = settings.supabase_service_key
    if key and len(key) > 8:
        text = text.replace(key, "***")
    return re.sub(r"eyJ[A-Za-z0-9_-]{10,}[A-Za-z0-9_.\-]*", "***", text)


def main() -> int:
    print("--------------------------------")
    print("STORAGE UPLOAD TEST")
    print("--------------------------------")
    shots = sorted(glob.glob(os.path.join("evidence", "*", "screenshot.jpg")))
    if not shots:
        print("Overall result: FAIL\nERROR: no Stage 5 screenshot found under evidence/*/")
        return 1
    src = shots[-1]
    size = os.path.getsize(src)
    print(f"Source: {src} ({size} bytes)")
    print(f"Dest: {BUCKET}/{DEST} (upsert)")

    try:
        from backend.storage.supabase_client import get_client
        client = get_client()
        with open(src, "rb") as fh:
            data = fh.read()
        assert len(data) == size and size > 0

        client.storage.from_(BUCKET).upload(
            DEST, data,
            {"content-type": "image/jpeg", "upsert": "true"})
        print("Upload response: OK")
    except Exception as exc:  # noqa: BLE001
        print(f"Overall result: FAIL\nERROR: {_scrub(str(exc))}")
        return 1

    try:
        back = client.storage.from_(BUCKET).download(DEST)
        raw = bytes(back) if not isinstance(back, (bytes, bytearray)) else back
        print(f"Verify download: {len(raw)} bytes (local {size} bytes)")
        ok = len(raw) == size
    except Exception as exc:  # noqa: BLE001
        print(f"Overall result: FAIL\nERROR: verify failed: {_scrub(str(exc))}")
        return 1

    print(f"\nOverall result: {'PASS' if ok else 'FAIL'}")
    if not ok:
        print("ERROR: size mismatch — upload corrupted?")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
