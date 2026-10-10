# Sentry — Resume Bullets & Keywords (Copy-Paste Ready)

Fill `[GitHub URL]` / `[Demo URL]` / `[Month Year]` before submitting.
Keep terminology: `Person Detected` / `Suspicious Activity` / `Incident` (never "theft").

---

## A. Recommended 3-bullet slot (FAANG-style, ATS-safe)

**Sentry — Real-Time AI Surveillance System** | *Python, FastAPI, OpenCV, YOLOv8, PyTorch, Supabase (Postgres + Storage), JavaScript, RTSP* | `[Month Year]` \
`[GitHub URL] | [Demo URL]`

- Engineered end-to-end surveillance pipeline ingesting RTSP from Tapo IP camera, running **YOLOv8n person detection (CPU-optimized)** at 2 FPS with stateful presence-rule engine flagging continuous loitering (>30s), reducing false alerts vs. naive per-frame detection.
- Built fault-tolerant **FastAPI backend with multithreaded worker architecture** (camera service + detection loop + rolling frame buffer decoupled); pre/post-event evidence capture (annotated JPEG + 10-sec MP4 with 4-sec pre-context) auto-uploaded to **Supabase Storage + Postgres**, with local fallback for zero data-loss on network failure.
- Developed responsive **incident-review dashboard (vanilla JS + MJPEG live stream)** with live feed, incident timeline, evidence viewer, and health APIs; hardened security via masked RTSP credentials, CORS allow-listing, and server-side-only secrets.

---

## B. Ultra-concise (1–2 lines, space-constrained)

**Sentry — AI CCTV Monitoring System** | *FastAPI, YOLOv8, OpenCV, Supabase, RTSP* \
Built real-time IP-camera surveillance with YOLOv8 person detection, rule-based loitering alerts, and automated screenshot + video evidence pipeline synced to Supabase with live web dashboard.

---

## C. Extended (portfolio / GitHub README / LinkedIn About)

**Sentry (SecureView) — Intelligent CCTV Monitoring for Retail / Campus Safety**

Traditional CCTV requires constant human monitoring. Sentry is an always-on AI pipeline: `Tapo RTSP → OpenCV → YOLOv8n → Rule Engine → Evidence Capture → Supabase → Dashboard`.

- CPU-only optimization: 640px inference + 2 FPS sampling → ~15× compute reduction, boxes rescaled to full-res for evidence.
- Stateful rules: rising-edge `PERSON_DETECTED` + continuous-presence `SUSPICIOUS_ACTIVITY` (3s gap tolerance, 1 alert/episode, 60–120s cooldown).
- Bounded-memory buffer: rolling 6-sec 320p/5 FPS pre-event context; fixed-length 10-sec MP4 (4s pre + 6s post).
- Failure isolation: camera, detection, upload fail independently; local retention on cloud failure.
- Optional NVIDIA NIM VLM caption layer (graceful degradation when unconfigured).

---

## D. LinkedIn post version

Building Sentry — real-time AI CCTV that turns any IP camera into an intelligent monitor. Python + FastAPI + YOLOv8 on CPU detects people, flags loitering via a custom rule engine, and auto-saves screenshot + 10s video evidence to Supabase with a live incident dashboard. Focused on edge efficiency (93% fewer inferences via smart sampling), fault-tolerance, and privacy-aware design. \
#ComputerVision #YOLO #FastAPI #Python #EdgeAI #Supabase #SystemDesign

---

## E. ATS keyword block (paste into skills or project tags)

**Languages:** Python 3, JavaScript (ES6), HTML5, CSS3 \
**Backend:** FastAPI, Uvicorn, Pydantic, Multithreading, REST APIs, MJPEG Streaming \
**CV/AI:** OpenCV, Ultralytics YOLOv8n, PyTorch (CPU), NVIDIA NIM (VLM) \
**Cloud/Data:** Supabase Postgres, Supabase Storage, imageio-ffmpeg \
**Infra:** RTSP/IP cameras, dotenv config, CORS, Producer-Consumer, Circular Buffer, Git

---

## F. One-line variants (pick per JD emphasis)

- **CV-heavy JD:** Real-time YOLOv8n person-detection pipeline on CPU (OpenCV + PyTorch) with annotated evidence capture.
- **Backend-heavy JD:** Multithreaded FastAPI service (camera worker + inference loop + cloud publisher) with health/status APIs and MJPEG streaming.
- **Cloud-heavy JD:** Automated evidence sync to Supabase Storage + Postgres with local-fallback retention and signed-URL delivery.
- **Full-stack JD:** End-to-end surveillance system — RTSP ingestion, AI inference, cloud persistence, vanilla-JS incident dashboard.
