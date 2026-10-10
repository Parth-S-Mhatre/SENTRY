"""Stage 6 — Supabase connection test. Run from project root:
    python -m backend.test_supabase

Verifies the backend can init the client from .env and actually reach
the project (lists Storage buckets as an authenticated call). No data
is uploaded, created, or modified.

Exit 0 = PASS, 1 = FAIL. The service key is never printed.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import settings


def _scrub(text: str) -> str:
    """Remove anything that looks like a key/token from error output."""
    key = settings.supabase_service_key
    if key and len(key) > 8:
        text = text.replace(key, "***")
        text = text.replace(key[:10], "***")
    # Generic JWT-shaped fallback (service keys are JWTs).
    return re.sub(r"eyJ[A-Za-z0-9_-]{10,}[A-Za-z0-9_.\-]*", "***", text)


def main() -> int:
    print("--------------------------------")
    print("SUPABASE CONNECTION TEST")
    print("--------------------------------")
    print(f"URL configured: {'yes' if settings.supabase_url else 'NO'}")
    print(f"Service key configured: "
          f"{'yes (' + str(len(settings.supabase_service_key)) + ' chars)' if settings.supabase_service_key else 'NO'}")

    try:
        from backend.storage.supabase_client import get_client
        client = get_client()
        print("Client init: PASS")
    except Exception as exc:  # noqa: BLE001
        print(f"Client init: FAIL\nERROR: {_scrub(str(exc))}")
        print("Overall result: FAIL")
        return 1

    try:
        buckets = client.storage.list_buckets()
        names = sorted(b.name for b in buckets)
        print(f"Authenticated Storage call: PASS ({len(names)} bucket(s): "
              f"{', '.join(names) if names else 'none yet'})")
    except Exception as exc:  # noqa: BLE001
        print(f"Authenticated Storage call: FAIL\nERROR: {_scrub(str(exc))}")
        print("Overall result: FAIL")
        return 1

    print("\nOverall result: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
