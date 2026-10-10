"""Sentry backend — FastAPI app: health, camera status, incident APIs,
evidence redirects, and the MJPEG live stream.

The background CameraService lives on app.state so routers share the
single RTSP connection. Route logic lives in backend/api/routes.py;
Supabase reads in backend/storage/evidence.py.
"""
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.camera.service import CameraService
from backend.config import mask_rtsp_url, settings


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    url = settings.rtsp_url_effective
    app.state.camera = None
    app.state.pipeline = None
    if url:
        try:
            cam = CameraService(url, timeout_sec=settings.rtsp_timeout_seconds)
            cam.start()
            app.state.camera = cam
        except Exception:
            app.state.camera = None  # status reports not running; never crash boot
        if app.state.camera and settings.pipeline_enabled:
            try:
                from backend.pipeline.worker import PipelineWorker
                worker = PipelineWorker(app.state.camera)
                worker.start()
                app.state.pipeline = worker
            except Exception:
                app.state.pipeline = None  # detection off; camera/API unaffected
    yield
    if app.state.pipeline:
        app.state.pipeline.stop()
        app.state.pipeline = None
    if app.state.camera:
        app.state.camera.stop()
        app.state.camera = None


app = FastAPI(title="Sentry", version="0.7.0", lifespan=lifespan)

_origins = [o.strip() for o in os.getenv("FRONTEND_ORIGIN", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],  # locked to FRONTEND_ORIGIN when set
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root() -> dict:
    return {"service": "Sentry", "status": "ok", "stage": 7}


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "sentry-backend", "stage": 7}


def _live_status(request: Request) -> dict[str, Any]:
    camera = getattr(request.app.state, "camera", None)
    if camera is None:
        return {"running": False, "reason": "not configured or failed to start"}
    try:
        status = camera.get_status()
    except Exception:  # noqa: BLE001 — report, don't crash status
        return {"running": False, "reason": "status error"}
    pipeline = getattr(request.app.state, "pipeline", None)
    try:
        status["pipeline"] = pipeline.status if pipeline else {"running": False}
    except Exception:  # noqa: BLE001
        status["pipeline"] = {"running": False}
    return status


@app.get("/api/camera/status")
def camera_status(request: Request) -> dict:
    url = settings.rtsp_url_effective
    configured = bool(url)
    creds_set = bool(settings.tapo_username and settings.tapo_password)
    live = _live_status(request)
    if live.get("running") and live.get("connected"):
        state = "online"
    elif live.get("running"):
        state = "connecting"
    else:
        state = "configured" if configured else "not_configured"
    return {
        "camera": settings.camera_name,
        "cameraId": settings.camera_id,
        "ip": settings.tapo_ip or "not configured",
        "port": settings.tapo_rtsp_port,
        "stream": settings.tapo_stream,
        # Never leak credentials: masked presence flag only.
        "rtsp": mask_rtsp_url(url),
        "configured": configured,
        "credentialsSet": creds_set,
        "status": state,
        "live": live,
    }
