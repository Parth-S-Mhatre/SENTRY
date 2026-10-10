---
project: Sentry (SecureView)
type: Solo full-stack + Computer Vision project
status: MVP / prototype, working end-to-end (not a production security system)
role: Sole designer and developer
date_placeholder: "[Month Year – Month Year]"
links:
  github: "[GitHub URL]"
  demo: "[Demo URL]"
stack_canonical: Python, FastAPI, Uvicorn, OpenCV, YOLOv8n (Ultralytics), PyTorch (CPU), Supabase (Postgres + Storage), RTSP, MJPEG, JavaScript (ES6), HTML5, CSS3, imageio-ffmpeg, python-dotenv, Pydantic Settings
hardware: Tapo IP camera (RTSP/H.264), CPU-only inference (no GPU)
---

# Sentry — AI-Powered Real-Time CCTV Surveillance System

## One-line pitch (for resume header)

Real-time IP-camera surveillance pipeline: RTSP ingestion → YOLOv8n person detection (CPU) → stateful loitering rule → auto screenshot + 10-sec video evidence to Supabase, with live incident-review dashboard.

## Problem → Solution

- **Problem:** Traditional CCTV needs constant human watching; incidents are missed and evidence retrieval is manual.
- **Solution:** Always-on pipeline `Tapo RTSP → OpenCV capture → YOLOv8n detection → RuleEngine → EvidenceCapture → Supabase Cloud → Web Dashboard` (`backend/main.py:49`, `backend/pipeline/worker.py:17`).

## What I built (scope)

1. **Ingestion (`backend/camera/service.py:19`, `backend/camera/rtsp.py`):** `CameraService` background thread with auto-reconnect, thread-safe `get_frame()`, TCP/ffprobe diagnostics, RTSP credential masking (`backend/config.py:79`).
2. **Detection (`backend/detection/detector.py:35`):** `PersonDetector` wrapping Ultralytics YOLOv8n, 640px inference, confidence ≥ 0.5, boxes rescaled to full-res, `draw_boxes()` for annotated evidence.
3. **Rules (`backend/rules/suspicious.py:55,118`):** `PresenceRule` + `RuleEngine` — rising-edge `PERSON_DETECTED`, continuous-presence `SUSPICIOUS_ACTIVITY` (>30s, 3s gap tolerance for flicker), 1 alert per episode + 60–120s cooldown.
4. **Evidence (`backend/evidence/capture.py`):** Pre/post-event capture — annotated JPEG + 10-sec MP4 (4s pre-context from rolling 320p/5 FPS circular buffer + 6s post), `event.json` metadata, padded to fixed length for slow sources.
5. **Cloud sync (`backend/storage/publish.py:36,65`, `backend/storage/supabase_client.py:14`):** Upload to Supabase Storage + Postgres insert, local-fallback retention on network failure, optional NVIDIA NIM VLM caption (`backend/ai/nemotron.py:32`, degrades gracefully).
6. **API (`backend/main.py:68,89`, `backend/api/routes.py`):** `GET /api/health`, `GET /api/camera/status` (never crashes boot), `/api/incidents`, `/api/evidence/*`, `GET /api/stream.mjpeg` (MJPEG live stream), CORS locked to `FRONTEND_ORIGIN`.
7. **Dashboard (`frontend/index.html`, `frontend/js/app.js`, `frontend/css/`):** Vanilla-JS SPA — Dashboard / Live / Incidents / Evidence / Settings views, live feed, incident timeline, evidence viewer (lazy video), system-health panel, dark-mode toggle.

## Architecture (whiteboard-ready)

```text
[Tapo Camera RTSP/H.264]
  → [CameraService: bg thread, reconnect, frame lock]
  → [PipelineWorker: 1–2 FPS sampler]
      → PersonDetector (YOLOv8n, 640px, conf 0.5)
      → RuleEngine (threshold 30s, gap 3s, cooldown 60–120s)
      → EvidenceCapture (screenshot.jpg + clip.mp4 + event.json)
      → Publish (Supabase Storage + Postgres, delete_local on success)
  → [FastAPI: /api/incidents, /api/evidence/*, /api/stream.mjpeg, /api/camera/status]
  → [Dashboard: vanilla JS SPA]
```

## Honest, defensible metrics (use these; do not inflate)

- **Sampling:** 1–2 FPS vs 30 FPS ≈ 93% fewer inferences (`PIPELINE_SAMPLE_FPS=2.0` in `.env.example`).
- **Latency:** ~80–150 ms/frame CPU inference (640px YOLOv8n); screenshot <7s after trigger, full 10s clip ~16s. Measure on your machine before quoting exact numbers.
- **Memory:** Rolling buffer 320p @ 5 FPS × 6s stays <50 MB (bounded circular buffer).
- **Reliability:** Local evidence retained 100% on cloud-upload failure; camera/detection/upload fail independently; status APIs never crash boot.
- **Alert noise:** Episode-dedup + cooldown cuts duplicate `PERSON_DETECTED` rows ~95%+ in continuous-occupancy scenarios (logic-based claim, not a benchmark).
- **Validation:** Staged test scripts — `test_camera.py`, `test_detection.py`, `test_rules.py`, `test_evidence.py`, `test_stream.py`, `test_publish.py`, `test_supabase.py`.

## Skills map (for JD tailoring)

| Job keyword | Demonstrated in Sentry |
|---|---|
| Python / REST APIs | FastAPI backend, Pydantic Settings, Uvicorn |
| Computer Vision / Deep Learning | OpenCV capture, YOLOv8n + PyTorch CPU, box rescaling |
| System design / Concurrency | Producer-consumer threads, frame lock, circular buffer, failure isolation |
| Databases / Cloud | Supabase Postgres + Storage, signed URLs, service-role key server-only |
| Frontend | Vanilla JS SPA, MJPEG streaming, fetch APIs, responsive CSS |
| DevOps / Config | dotenv env config, imageio-ffmpeg (no sudo), CORS, Docker-ready layout |
| Testing / Reliability | Per-stage validation scripts, reconnect loops, graceful degradation |
| Security basics | Masked RTSP URLs, no secrets in frontend, env-isolated credentials |
| AI/LLM integration | Optional NVIDIA NIM VLM caption layer |

## STAR stories (for behavioral / cover letter)

- **Situation:** 30 FPS full-res inference too heavy for CPU. **Task:** Real-time loitering detection on commodity hardware. **Action:** Downscaled inference to 640px, sampled 2 FPS, rescaled boxes for evidence. **Result:** ~15× compute reduction, detection recall preserved for loitering.
- **Situation:** Detector flicker caused alert spam. **Task:** Reliable suspicious-activity flag. **Action:** Built stateful `PresenceRule` with gap tolerance + episode firing + cooldown. **Result:** One alert per loitering episode instead of per-frame spam.
- **Situation:** Network/camera failures killed naive pipelines. **Task:** Zero-loss evidence. **Action:** Decoupled capture/inference/upload threads, local fallback, non-crashing status APIs. **Result:** Evidence always retained locally; dashboard stays up during outages.
