"""Nemotron focused test. Run from project root:
    python -m backend.test_nemotron

Takes the latest Stage 5/6 evidence screenshot, downscales it (bound
the API payload), and asks Nemotron for a scene description. PASS =
non-empty analysis text. The key is never printed (length only, and
all output is scrubbed).

Exit 0 = PASS, 1 = FAIL.
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2

from dotenv import load_dotenv

load_dotenv()  # before reading NVIDIA_* for the report

MAX_W = 768


def _scrub(text: str, key: str) -> str:
    if key and len(key) > 8:
        text = text.replace(key, "***")
    return re.sub(r"eyJ[A-Za-z0-9_-]{10,}[A-Za-z0-9_.\-]*|nvapi-[A-Za-z0-9_-]+",
                  "***", text)


def main() -> int:
    print("--------------------------------")
    print("NEMOTRON TEST")
    print("--------------------------------")
    key = os.getenv("NVIDIA_API_KEY", "")
    model = os.getenv("NVIDIA_MODEL", "")
    print(f"API key: {'set (' + str(len(key)) + ' chars)' if key else 'MISSING'}")
    print(f"Model: {model or 'MISSING'}")

    shots = sorted(glob.glob(os.path.join("evidence", "*", "screenshot.jpg")))
    if not shots:
        print("Overall result: FAIL\nERROR: no evidence screenshot found")
        return 1
    src = shots[-1]
    img = cv2.imread(src)
    if img is None:
        print(f"Overall result: FAIL\nERROR: cannot read {src}")
        return 1
    h, w = img.shape[:2]
    if w > MAX_W:
        img = cv2.resize(img, (MAX_W, int(h * MAX_W / w)))
    ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
    assert ok
    payload = jpg.tobytes()
    print(f"Image: {src} -> {len(payload)} bytes @ {img.shape[1]}px wide")

    from backend.ai.nemotron import analyze_image
    print("Calling Nemotron...", flush=True)
    res = analyze_image(payload)
    status = "PASS" if res["ok"] and res["text"] else "FAIL"
    print(f"Analysis: {status}")
    if res["ok"]:
        print(f"--- model: {res['model']}\n{_scrub(res['text'], key)}")
    else:
        print(f"ERROR: {_scrub(res['error'], key)}")
    print(f"\nOverall result: {'PASS' if res['ok'] and res['text'] else 'FAIL'}")
    return 0 if res["ok"] and res["text"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
