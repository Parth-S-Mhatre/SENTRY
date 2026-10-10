"""Stage 7 — API tests. Run from project root:
    python -m backend.test_api

Uses TestClient (lifespan starts the real camera service) and real
Supabase data. Covers health, camera status, incident list/detail,
404s, 400s, evidence redirects, and MJPEG stream bytes.

Exit 0 = PASS, 1 = FAIL. Secrets never asserted or printed.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from backend.config import settings
from backend.main import app

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{name}] {'PASS' if cond else 'FAIL'} {detail}")
    if not cond:
        FAILURES.append(name)


def main() -> int:
    print("--------------------------------")
    print("API TEST")
    print("--------------------------------")
    key = settings.supabase_service_key
    with TestClient(app) as c:
        r = c.get("/api/health")
        check("health", r.status_code == 200 and r.json().get("status") == "ok",
              f"{r.status_code}")

        body = {"status": "connecting"}
        for _ in range(20):  # allow the background reader to connect
            r = c.get("/api/camera/status")
            body = r.json()
            if body.get("status") == "online":
                break
            time.sleep(0.5)
        check("camera-status", r.status_code == 200 and body.get("status") == "online",
              f"status={body.get('status')}")
        check("no-secrets", "dhruvparth" not in r.text and (not key or key not in r.text),
              "no password/key in body")

        r = c.get("/api/incidents")
        body = r.json()
        rows = body.get("incidents", [])
        dates = [x.get("created_at", "") for x in rows]
        check("incidents-list", r.status_code == 200 and body.get("count") == len(rows)
              and dates == sorted(dates, reverse=True),
              f"count={body.get('count')}")
        r = c.get("/api/incidents?limit=1")
        check("incidents-limit", r.status_code == 200 and r.json().get("count") <= 1, "")

        for bad in ("0", "101"):
            r = c.get(f"/api/incidents?limit={bad}")
            check(f"limit-{bad}-400", r.status_code == 400, f"{r.status_code}")

        fake = "00000000-0000-0000-0000-000000000000"
        r = c.get(f"/api/incidents/{fake}")
        check("missing-404", r.status_code == 404, f"{r.status_code}")

        iid = rows[0]["id"] if rows else fake
        r = c.get(f"/api/incidents/{iid}")
        check("incident-detail", r.status_code == 200 and r.json().get("id") == iid,
              f"id={iid[:8]}...")

        if rows:
            r = c.get(f"/api/incidents/{iid}/screenshot", follow_redirects=False)
            loc = r.headers.get("location", "")
            check("screenshot-redirect",
                  r.status_code == 307 and loc.startswith("https://")
                  and (not key or key not in loc), f"{r.status_code}")
            with_clip = next((x for x in rows if x.get("clip_path")), None)
            if with_clip:
                r = c.get(f"/api/incidents/{with_clip['id']}/clip", follow_redirects=False)
                loc = r.headers.get("location", "")
                check("clip-redirect",
                      r.status_code == 307 and loc.startswith("https://")
                      and (not key or key not in loc), f"{r.status_code}")
            else:
                check("clip-redirect", False, "no clip incident in DB")
            r = c.get(f"/api/incidents/{fake}/screenshot", follow_redirects=False)
            check("evidence-missing-404", r.status_code == 404, f"{r.status_code}")
        else:
            print("  (no incidents in DB — redirect checks skipped)")

        # MJPEG: TestClient's transport can't complete an infinite
        # stream, so exercise the real generator (live camera frames ->
        # 480p JPEG chunks) directly; HTTP delivery is verified with curl
        # against a running server.
        try:
            from backend.api.routes import _mjpeg_frames
            gen = _mjpeg_frames(app.state.camera)
            chunks = [next(gen) for _ in range(2)]
            try:
                gen.close()
            except Exception:
                pass
            buf = b"".join(chunks)
            njpg = buf.count(b"\xff\xd8\xff")
            check("stream-frames", all(x.startswith(b"--frame") for x in chunks)
                  and njpg == 2, f"{len(buf)} bytes, {njpg} jpegs")
            routes = [getattr(r, "path", "") for r in app.routes]
            check("stream-route", "/api/stream" in routes, "")
        except Exception as exc:
            check("stream-frames", False, f"{type(exc).__name__}")

    print(f"\nOverall result: {'PASS' if not FAILURES else 'FAIL ' + str(FAILURES)}")
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
