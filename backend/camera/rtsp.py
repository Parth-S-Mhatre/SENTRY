"""RTSP helpers. Used by test_camera.py and later by the video pipeline.

Transport: TCP (more reliable than UDP for Tapo over Wi-Fi).
Probing order: system ffprobe (if installed) -> bundled ffmpeg binary
(imageio-ffmpeg, user-space, no sudo needed) -> OpenCV frame decode.
Frame decode via OpenCV is the acceptance criterion; probes are diagnostic.
"""
import shutil
import socket
import subprocess
import time
from typing import Any, Optional

import cv2


def ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def ffmpeg_exe() -> Optional[str]:
    """System ffmpeg, else bundled imageio-ffmpeg binary, else None."""
    sys_ff = shutil.which("ffmpeg")
    if sys_ff:
        return sys_ff
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def tcp_reachable(host: str, port: int, timeout_sec: int = 5) -> tuple[bool, str]:
    """Stage-1 reachability: can we open TCP host:port at all?"""
    if not host:
        return False, "no host configured (set TAPO_IP in .env)"
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True, f"TCP {host}:{port} reachable"
    except socket.timeout:
        return False, f"timeout reaching {host}:{port} (camera offline or not on same LAN?)"
    except ConnectionRefusedError:
        return False, f"connection refused by {host}:{port} (wrong IP/port or RTSP disabled?)"
    except OSError as exc:
        return False, f"unreachable {host}:{port}: {exc} (wrong IP or PC not on camera LAN?)"


def ffprobe_stream(url: str, timeout_sec: int = 10) -> dict:
    """Best-effort stream probe. {}-style dict if unavailable/failing."""
    if not ffprobe_available():
        return {"available": False, "reason": "ffprobe not installed"}
    cmd = [
        "ffprobe", "-v", "error",
        "-rtsp_transport", "tcp",
        "-timeout", str(timeout_sec * 1_000_000),
        "-show_entries", "stream=width,height,avg_frame_rate,codec_name",
        "-of", "default=noprint_wrappers=1",
        url,
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec + 5)
        info: dict[str, Any] = {
            "available": True, "raw": out.stdout.strip(),
            "stderr": out.stderr.strip()[-500:],
        }
        for line in out.stdout.splitlines():
            if "=" in line:
                k, v = line.strip().split("=", 1)
                info[k] = v
        return info
    except Exception as exc:  # noqa: BLE001 — report, don't crash
        return {"available": False, "reason": f"ffprobe error: {exc}"}


def ffmpeg_probe(url: str, timeout_sec: int = 10) -> dict:
    """Fallback probe using `ffmpeg -i` stderr (works with bundled binary).

    Parses lines like: Stream #0:0: Video: h264 (...), 1920x1080, 15 fps
    Never includes the URL (and thus never the password) in output.
    """
    exe = ffmpeg_exe()
    if not exe:
        return {"available": False, "reason": "no ffmpeg binary available"}
    cmd = [exe, "-hide_banner", "-rtsp_transport", "tcp",
           "-timeout", str(timeout_sec * 1_000_000),
           "-i", url, "-t", "1", "-f", "null", "-"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec + 5)
        err = out.stderr or ""
        info: dict[str, Any] = {"available": True}
        for line in err.splitlines():
            s = line.strip()
            if "Video:" in s:
                # e.g. "Stream #0:0: Video: h264 (Main), yuvj420p(...), 1920x1080, 15 fps, ..."
                try:
                    after = s.split("Video:", 1)[1].strip()
                    info["codec_name"] = after.split(",", 1)[0].split("(")[0].strip()
                except Exception:
                    pass
                import re
                m = re.search(r"(\d{3,5})x(\d{3,5})", s)
                if m:
                    info["width"], info["height"] = m.group(1), m.group(2)
                m = re.search(r"(\d+(?:\.\d+)?)\s*fps", s)
                if m:
                    info["avg_frame_rate"] = m.group(1)
                info["video_line"] = s[:200]
                break
        if "codec_name" not in info:
            info["available"] = False
            # Sanitized tail: strip any accidental URL echo (ffmpeg echoes the
            # input URL on errors, which would leak the password into logs).
            tail = "\n".join(err.splitlines()[-8:])
            info["reason"] = _sanitize(tail)[-400:]
        return info
    except subprocess.TimeoutExpired:
        return {"available": False, "reason": "ffmpeg probe timed out (camera not responding?)"}
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": f"ffmpeg probe error: {exc}"}


def _sanitize(text: str) -> str:
    """Remove rtsp://... credentials from diagnostic text."""
    import re
    return re.sub(r"rtsp://\S+", "rtsp://****", text)


def open_stream(url: str, timeout_sec: int = 10) -> "cv2.VideoCapture":
    """Open RTSP over TCP (more reliable than UDP for Tapo)."""
    try:
        cv2.setUseOptimized(True)
    except Exception:
        pass
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_sec * 1000)
    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_sec * 1000)
    return cap


def diagnose_failure(url: str, opened: bool, frame_ok: bool) -> str:
    """Map a failure to the most likely human-readable cause."""
    if not url or "CAMERA_IP" in url or "USERNAME" in url:
        return "invalid RTSP URL (placeholder/example URL — set real credentials in .env)"
    lower = url.lower()
    if not lower.startswith("rtsp://"):
        return "invalid RTSP URL (must start with rtsp://)"
    if "@" not in url:
        return "authentication failure likely (no userinfo user:pass@ in RTSP URL)"
    if not opened:
        return ("connection refused / timeout / camera unreachable — check: "
                "camera IP, port 554 reachable, camera + PC on same LAN, "
                "wrong username/password (remember @ -> %40), "
                "or Tapo stream1/stream2 name")
    if opened and not frame_ok:
        return ("connected but frame decoding failed — possible codec/decoder "
                "problem, network interruption, or wrong stream path")
    return "unknown — check network problem / camera logs"


def validate_rtsp(url: str, timeout_sec: int = 10,
                  save_path: str = "test_output/test_frame.jpg",
                  host: str = "", port: int = 554) -> dict:
    """Full Stage-1 validation. Never raises — returns a result dict."""
    result: dict[str, Any] = {
        "reachable": "FAIL", "reach_detail": "",
        "connection": "FAIL", "authentication": "UNKNOWN",
        "video_stream": "FAIL", "frame_decoding": "FAIL",
        "codec": "unknown", "resolution": "unknown", "fps": "unknown",
        "first_frame": "FAIL", "error": "", "save_path": save_path,
        "ffprobe": {}, "ffmpeg": {},
    }
    if not url:
        result["error"] = ("invalid RTSP URL (no credentials — set TAPO_USERNAME, "
                           "TAPO_PASSWORD, TAPO_IP in .env)")
        result["reach_detail"] = result["error"]
        return result

    if host:
        ok, detail = tcp_reachable(host, port, timeout_sec=min(timeout_sec, 8))
        result["reachable"] = "PASS" if ok else "FAIL"
        result["reach_detail"] = detail
        if not ok:
            result["error"] = detail
            # Still attempt decode? No — TCP closed means decode cannot work.
            return result
    else:
        result["reachable"] = "UNKNOWN"
        result["reach_detail"] = "no host given, skipped TCP check"

    result["ffprobe"] = ffprobe_stream(url, timeout_sec)
    result["ffmpeg"] = ffmpeg_probe(url, timeout_sec)
    probe = result["ffprobe"] if result["ffprobe"].get("codec_name") else result["ffmpeg"]
    if probe.get("codec_name"):
        result["codec"] = str(probe["codec_name"])
        result["video_stream"] = "PASS"

    cap: Optional[cv2.VideoCapture] = None
    try:
        t0 = time.time()
        cap = open_stream(url, timeout_sec)
        opened = cap.isOpened()
        result["connection"] = "PASS" if opened else "FAIL"
        if not opened:
            result["error"] = diagnose_failure(url, opened=False, frame_ok=False)
            return result

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = cap.get(cv2.CAP_PROP_FPS) or 0

        ok, frame = cap.read()
        elapsed = time.time() - t0
        if ok and frame is not None:
            result["frame_decoding"] = "PASS"
            result["first_frame"] = "PASS"
            result["video_stream"] = "PASS"
            result["authentication"] = "PASS"
            h, w = frame.shape[:2]
            width, height = (w, h) if w and h else (width, height)
            if width and height:
                result["resolution"] = f"{width}x{height}"
            elif probe.get("width") and probe.get("height"):
                result["resolution"] = f"{probe['width']}x{probe['height']}"
            try:
                if fps and fps < 120:
                    result["fps"] = f"{fps:.0f}"
                elif probe.get("avg_frame_rate"):
                    result["fps"] = str(probe["avg_frame_rate"])
            except Exception:
                pass
            import os
            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
            cv2.imwrite(save_path, frame)
            result["first_frame_ms"] = int(elapsed * 1000)
        else:
            result["error"] = ("authentication failure likely (opened stream but "
                               "received no frames — verify Tapo username/password, "
                               "URL-encode @ as %40, and stream1 vs stream2 path)")
            result["authentication"] = "FAIL?"
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{diagnose_failure(url, opened=False, frame_ok=False)} | detail: {exc}"
    finally:
        try:
            if cap is not None:
                cap.release()
        except Exception:
            pass
    if result["first_frame"] == "FAIL" and not result["error"]:
        result["error"] = diagnose_failure(url, opened=(result["connection"] == "PASS"), frame_ok=False)
    return result
