"""Stage 1 — RTSP camera validation.

Run from project root:
    python -m backend.test_camera
or:
    python backend/test_camera.py

Verifies (against 192.168.1.4:554 by default, from .env):
RTSP reachability, authentication, stream, codec, frame decoding,
resolution, FPS, first frame. Saves test_output/test_frame.jpg.

Exit code 0 = PASS, 1 = FAIL. Never prints secrets.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.camera.rtsp import ffmpeg_exe, ffprobe_available, validate_rtsp
from backend.config import mask_rtsp_url, settings

SAVE_PATH = os.path.join("test_output", "test_frame.jpg")


def main() -> int:
    url = settings.rtsp_url_effective.strip()
    print("--------------------------------")
    print("CAMERA VALIDATION")
    print("--------------------------------")
    print(f"Camera: {settings.camera_name} ({settings.camera_id})")
    print(f"Target: {settings.tapo_ip or 'not configured'}:{settings.tapo_rtsp_port} "
          f"stream={settings.tapo_stream}")
    print(f"RTSP URL: {mask_rtsp_url(url)}")
    print(f"Credentials: {'set' if settings.tapo_username and settings.tapo_password else 'MISSING (set TAPO_USERNAME + TAPO_PASSWORD in .env)'}")
    print(f"ffprobe: {'available' if ffprobe_available() else 'not installed'} | "
          f"ffmpeg: {ffmpeg_exe() or 'not found'}")
    print()

    res = validate_rtsp(url, timeout_sec=settings.rtsp_timeout_seconds,
                        save_path=SAVE_PATH,
                        host=settings.tapo_ip, port=settings.tapo_rtsp_port)

    print(f"RTSP reachable: {res['reachable']} ({res['reach_detail']})")
    print(f"Connection: {res['connection']}")
    print(f"Authentication: {res['authentication']}")
    print(f"Stream detected: {res['video_stream']}")
    print(f"Codec: {res['codec']}")
    print(f"Frame decoding: {res['frame_decoding']}")
    print(f"Resolution: {res['resolution']}")
    print(f"FPS: {res['fps']}")
    print(f"Frame decoded: {res['first_frame']}")
    print(f"test_frame.jpg created: {'PASS' if os.path.exists(SAVE_PATH) and res['first_frame'] == 'PASS' else 'FAIL'}")
    ff = res.get("ffprobe") or {}
    if ff.get("available") and ff.get("raw"):
        print(f"ffprobe: {ff['raw'][:200]}")
    fm = res.get("ffmpeg") or {}
    if fm.get("video_line"):
        print(f"ffmpeg: {fm['video_line']}")
    print()

    overall = "PASS" if res["first_frame"] == "PASS" else "FAIL"
    print(f"Overall result: {overall}")
    if overall == "PASS":
        print(f"Test frame saved to: {SAVE_PATH}")
    else:
        print(f"ERROR: {res['error']}")
        print("NEXT STEP: put real Tapo credentials in .env (remember @ in "
              "password is auto-encoded to %40), verify PC and camera share "
              "the same LAN (ping 192.168.1.4, TCP 554 open), try stream1 vs stream2.")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
