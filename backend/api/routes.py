"""Stage 7 — API routes consumed by the future Vanilla JS frontend.

Incidents + evidence read from Supabase; the MJPEG stream reuses the
existing in-memory CameraService (no second RTSP connection). Errors
are clean JSON with no secrets or stack traces.
"""
import time
from typing import Any

import cv2
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, StreamingResponse

from backend.storage import evidence as store

router = APIRouter(prefix="/api")

STREAM_W, STREAM_H = 854, 480  # ~480p, low-bandwidth
STREAM_FPS = 10
STREAM_JPEG_QUALITY = 70
DETECT_EVERY_N_FRAMES = 5  # YOLO at ~2fps; last boxes reused between runs

_detector = None
_detector_ok = True
_last_boxes: list = []
_frame_n = 0


def _annotate(frame):
    """Draw last-known person boxes; refresh via YOLO every Nth frame.

    Reuses the existing PersonDetector on the already-flowing frames —
    no second RTSP connection. Any detector failure degrades to raw
    frames (never breaks the stream).
    """
    global _detector, _detector_ok, _last_boxes, _frame_n
    _frame_n += 1
    if _detector_ok and _frame_n % DETECT_EVERY_N_FRAMES == 0:
        try:
            if _detector is None:
                from backend.detection.detector import PersonDetector
                _detector = PersonDetector()
                _detector._load()  # noqa: SLF001
            small = cv2.resize(frame, (640, 360))
            dets = _detector.detect(small)
            sx, sy = frame.shape[1] / 640, frame.shape[0] / 360
            _last_boxes = list(dets)
            for d in _last_boxes:  # scale boxes back to full-frame coords
                x1, y1, x2, y2 = d.bbox
                d.bbox = (int(x1 * sx), int(y1 * sy), int(x2 * sx), int(y2 * sy))
        except Exception:
            _detector_ok = False  # noqa: BLE001 — stream raw from here on
            _last_boxes = []
    if not _last_boxes:
        return frame
    from backend.detection.detector import draw_boxes
    return draw_boxes(frame, _last_boxes)

not_found = lambda what="incident": HTTPException(404, f"{what} not found")


def _supabase_or_500(action: str) -> Any:
    """Run a Supabase read; config/auth/outage -> 500 without details."""
    try:
        return action()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(500, "storage backend unavailable")


@router.get("/incidents")
def incidents(limit: int = Query(default=20)) -> dict:
    if not 1 <= limit <= 100:
        raise HTTPException(400, "limit must be between 1 and 100")
    rows = _supabase_or_500(lambda: store.list_incidents(limit))
    return {"incidents": rows, "count": len(rows)}


@router.get("/incidents/{incident_id}")
def incident(incident_id: str) -> dict:
    row = _supabase_or_500(lambda: store.get_incident(incident_id))
    if not row:
        raise not_found()
    return row


def _evidence_redirect(incident_id: str, kind: str) -> RedirectResponse:
    row = _supabase_or_500(lambda: store.get_incident(incident_id))
    if not row:
        raise not_found()
    key = "screenshot_path" if kind == "screenshot" else "clip_path"
    url = _supabase_or_500(lambda: store.signed_url(row.get(key) or ""))
    if not url:
        raise not_found("evidence")
    return RedirectResponse(url, status_code=307)


@router.get("/incidents/{incident_id}/screenshot")
def screenshot(incident_id: str) -> RedirectResponse:
    return _evidence_redirect(incident_id, "screenshot")


@router.get("/incidents/{incident_id}/clip")
def clip(incident_id: str) -> RedirectResponse:
    return _evidence_redirect(incident_id, "clip")


def _mjpeg_frames(camera: Any):
    """Yield 480p JPEG frames until the client goes away."""
    deadline = time.time() + 5.0
    while time.time() < deadline:  # wait for first frame, else 503 upstream
        frame = camera.get_frame() if camera else None
        if frame is not None:
            break
        time.sleep(0.2)
    else:
        return
    period = 1.0 / STREAM_FPS
    while True:
        t0 = time.time()
        try:
            frame = camera.get_frame()
            if frame is None:
                time.sleep(0.2)
                continue
            small = cv2.resize(_annotate(frame), (STREAM_W, STREAM_H))
            ok, jpg = cv2.imencode(
                ".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, STREAM_JPEG_QUALITY])
            if not ok:
                continue
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" +
                   jpg.tobytes() + b"\r\n")
        except (GeneratorExit, Exception):
            break  # client disconnect / encode hiccup: end stream quietly
        dt = time.time() - t0
        if dt < period:
            time.sleep(period - dt)


@router.get("/stream")
def stream(request: Request) -> StreamingResponse:
    camera = getattr(request.app.state, "camera", None)
    if camera is None or not getattr(camera, "is_running", False):
        raise HTTPException(503, "camera stream unavailable")
    gen = _mjpeg_frames(camera)
    try:
        first = next(gen)
    except StopIteration:
        raise HTTPException(503, "no camera frame available")

    def chained():  # re-yield first frame, then the rest
        yield first
        yield from gen

    return StreamingResponse(
        chained(), media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache"})
