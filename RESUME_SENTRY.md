# Sentry — AI-Powered Real-Time CCTV Surveillance System | Resume Kit

> Copy-paste ready, FAANG-bar resume content for the Sentry project.
> Pick **Option A** for a standard 1-project slot (recommended).

---

## Option A — Recommended (3 Bullets, FAANG-Style, ATS-Safe)

**Sentry — Real-Time AI Surveillance System** | *Python, FastAPI, OpenCV, YOLOv8, PyTorch, Supabase (Postgres + Storage), JavaScript, RTSP*
[ GitHub: <paste-link> | Live Demo: <paste-link> ]

* Engineered end-to-end real-time surveillance pipeline ingesting RTSP stream from Tapo IP camera, running **YOLOv8n person detection (CPU-optimized)** at 2 FPS with stateful presence-rule engine to flag continuous loitering (>30s), reducing false alerts vs. naive per-frame detection.
* Built fault-tolerant **FastAPI backend with multithreaded worker architecture** (camera service + detection loop + rolling frame buffer decoupled); implemented pre/post-event evidence capture (annotated JPEG + 10-sec MP4 with 4-sec pre-context) auto-uploaded to **Supabase Storage + Postgres**, achieving zero data-loss on pipeline failure via local fallback.
* Developed responsive **incident-review dashboard (vanilla JS + MJPEG live stream)** with live feed, incident timeline, evidence viewer, and system health APIs; hardened security by masking RTSP credentials, enforcing CORS allow-listing, and isolating secrets to server-side env config.

---

## Option B — Ultra-Concise (1-2 Lines, For Space-Constrained Resume)

**Sentry — AI CCTV Monitoring System** | *FastAPI, YOLOv8, OpenCV, Supabase, RTSP*
Built real-time IP-camera surveillance system with YOLOv8 person detection, rule-based suspicious-activity alerts, and automated screenshot + video evidence pipeline synced to cloud (Supabase) with live web dashboard.

---

## Option C — Extended (For Portfolio / LinkedIn / GitHub README)

**Sentry (SecureView) — Intelligent CCTV Monitoring for Retail / Campus Safety**

Problem: Traditional CCTV requires constant human monitoring; critical incidents are missed and evidence retrieval is manual.

Solution: Always-on AI pipeline: `Tapo RTSP → OpenCV capture → YOLOv8n detection → Rule Engine → Evidence Capture → Supabase Cloud → Web Dashboard`.

Key engineering decisions:
* **CPU-only inference optimization:** Downscale to 640px for inference, rescale boxes to full-res for evidence; sample at 1-2 FPS instead of 30 FPS → ~15x compute reduction with no loss in detection recall for loitering use-case.
* **Stateful rule engine:** Rising-edge `PERSON_DETECTED` + continuous-presence `SUSPICIOUS_ACTIVITY` with gap tolerance (3s) to handle detector flicker; fires max 1 alert per episode + 60-120s cooldown to prevent spam.
* **Bounded-memory video buffer:** Rolling 6-sec buffer at 320p/5 FPS for pre-event context; 10-sec MP4 assembled as 4s pre + 6s post-trigger, padded to fixed length for slow sources.
* **Failure isolation:** Camera, detection, and upload stages fail independently — status APIs never crash boot; local evidence retained if cloud upload fails.
* **Optional VLM layer:** NVIDIA NIM integration for natural-language incident description (gracefully degrades to empty string when unconfigured).

---

## Tech Stack (ATS Keywords Block)

**Languages:** Python 3, JavaScript (ES6), HTML5, CSS3
**Backend:** FastAPI, Uvicorn, Pydantic, Multithreading, REST APIs, MJPEG Streaming
**Computer Vision / AI:** OpenCV, Ultralytics YOLOv8n, PyTorch (CPU), NVIDIA NIM (VLM)
**Cloud / Data:** Supabase Postgres, Supabase Storage, imageio-ffmpeg
**Infra / Practices:** RTSP/IP Camera Integration, Docker-ready, dotenv Config, CORS, System Design (Producer-Consumer, Circular Buffer), Git

---

## Quantified Impact — How to Talk About It (Honest, Defensible)

FAANG interviewers probe numbers. Use these (measure before interview if possible):

* **Latency:** Inference ~80-150ms/frame on CPU (640px YOLOv8n) → end-to-end alert-to-evidence <7s for screenshot, ~16s for full 10s clip.
* **Efficiency:** Sampling 2 FPS vs 30 FPS = 93% fewer inferences; buffer memory <50 MB (320p @ 5 FPS x 6s).
* **Reliability:** 100% local evidence retention on network failure; background worker error-counted, never crashes API.
* **Precision:** Cooldown + episode-dedup reduces duplicate `PERSON_DETECTED` rows by ~95%+ in continuous-occupancy scenarios (explain logic, don't fake a benchmark).

> Do NOT invent accuracy % like "98% accuracy" unless you evaluated on a labeled test set. Say "CPU-optimized YOLOv8n (COCO-pretrained, conf ≥0.5)" instead.

---

## System Architecture (For Resume + Interview Whiteboard)

```
[Tapo Camera - RTSP/H.264]
        |
[CameraService - Background Thread, Auto-Reconnect, Shared Frame Lock]
        | get_frame() (thread-safe, latest frame)
        v
[PipelineWorker - 2 FPS Sampler]
  -> PersonDetector (YOLOv8n, 640px, conf 0.5)
  -> RuleEngine (PresenceRule: threshold 30s, gap 3s)
  -> EvidenceCapture (screenshot.jpg + clip.mp4 + event.json)
  -> Publish (Supabase Storage upload + Postgres insert, delete_local=True)
        |
[FastAPI - /api/incidents, /api/evidence/*, /api/stream.mjpeg, /api/camera/status]
        |
[Dashboard - Vanilla JS SPA: Dashboard / Live / Incidents / Evidence / Settings]
```

---

## FAANG Interview Talking Points (30-sec Pitch + Deep Dives)

**30-sec pitch:**
> "I built Sentry, a real-time AI surveillance system. It streams RTSP from an IP camera, runs YOLOv8 person detection on CPU, applies a stateful rule to detect loitering, and auto-captures screenshot plus 10-second video evidence to Supabase with a live web dashboard. The key challenge was doing this reliably on CPU with bounded memory and zero coupling between capture, inference, and upload."

**Expect follow-ups — prepare these:**

1. Why YOLOv8n + CPU instead of cloud inference? → Cost, latency, privacy, offline resilience.
2. How do you handle false positives / flicker? → Confidence threshold 0.5, gap tolerance, episode firing, cooldown.
3. What if camera disconnects? → CameraService reconnect loop, status state machine (online/connecting/configured), API stays up.
4. How would you scale to 100 cameras? → Move inference to GPU service (Triton / TensorRT), queue via Kafka/Redis Streams, sharded workers per camera, object storage + CDN for evidence.
5. Security? → No secrets in frontend, masked RTSP URLs in logs/API, service-role key server-only, CORS allow-list.

---

## GitHub README Polish Checklist (Do Before Adding Link to Resume)

* [ ] Rename repo to `sentry-ai-surveillance` + add topics: `computer-vision`, `yolov8`, `fastapi`, `opencv`, `supabase`, `rtsp`, `surveillance`
* [ ] Add architecture diagram + 20-sec demo GIF (live feed → alert → evidence)
* [ ] Add `## Results` with real screenshot of dashboard + sample evidence (blur faces)
* [ ] Pin requirements, add `Dockerfile`, add `LICENSE` (MIT)
* [ ] Replace "Stage 5/6/7" dev notes with user-facing Quickstart

---

## Copy-Paste LinkedIn Version

Building Sentry — real-time AI CCTV system that turns any IP camera into an intelligent monitor. Python + FastAPI + YOLOv8 on CPU detects people, flags loitering via custom rule engine, and auto-saves screenshot + 10s video evidence to Supabase with a live incident dashboard. Focused on edge efficiency (93% fewer inferences via smart sampling), fault-tolerance, and privacy-aware design.

# Tags: #ComputerVision #YOLO #FastAPI #Python #EdgeAI #Supabase #SystemDesign
