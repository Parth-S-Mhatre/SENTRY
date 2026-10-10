# SecureView (MVP / prototype — not a production security system)

Lightweight CCTV monitoring: Tapo camera (RTSP) → FastAPI + OpenCV →
person detection → suspicious-activity rule → screenshot + 10s clip →
Supabase Storage + Postgres → lightweight HTML/CSS/JS dashboard.

## Current status: Stage 5 passed (local evidence capture)

Proven so far: camera → frame pipeline → person detection →
suspicious-activity rule → screenshot + 10s clip on local disk.
Next: Stage 6 (revised) uploads evidence to Supabase Storage and writes
the incident row to Supabase Postgres. No dashboard yet.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env with your real Tapo RTSP URL (never commit .env)
```

## Validate camera (Stage 1)

```bash
python test_camera.py
```

Expected on success:

```
--------------------------------
CAMERA VALIDATION
--------------------------------
...
Overall result: PASS
```

Frame saved to `test_output/test_frame.jpg`.

## Run backend (Phase 1 smoke test)

```bash
uvicorn backend.main:app --reload --port 8000
curl http://localhost:8000/api/health
curl http://localhost:8000/api/camera/status
```

## Terminology

Use `Person Detected` / `Suspicious Activity` / `Potential Suspicious Activity` /
`Incident`. The admin reviews evidence — the AI never declares "theft".
