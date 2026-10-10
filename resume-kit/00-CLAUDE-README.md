# Claude Resume Kit — How to Use These Files

> These files describe the **Sentry** project for automated CV / resume generation.
> Load all files in `resume-kit/` when tailoring a resume, LinkedIn profile, or cover letter.

## Files

1. `01-sentry-project-context.md` — Source of truth. Project summary, role, architecture, tech stack, responsibilities, honest metrics. **Prefer this over guessing.**
2. `02-sentry-bullets-and-keywords.md` — Copy-paste resume bullets (1-line / 3-bullet / extended) + ATS keyword block + LinkedIn version.

Existing file (legacy, human-readable): `../RESUME_SENTRY.md` — keep for reference, but the two files above are canonical for LLM use.

## Rules for Claude

- Do NOT invent accuracy numbers (no "98% accuracy"). Use only the defensible metrics in `01-`.
- Do NOT claim team size > 1, production deployment, or multi-camera scale. This is a solo MVP/prototype with 1 Tapo IP camera.
- Do NOT claim "theft detection". Terminology is `Person Detected` / `Suspicious Activity` / `Incident`. AI flags, human reviews.
- Tailoring: pick bullets that match the job description keywords (see skills map in `01-`). Keep 2–3 bullets for a standard resume slot.
- Dates / links: fill `[Month Year]` and `[GitHub URL]` / `[Demo URL]` placeholders from user input. Never hallucinate URLs.
- Stack names must match exactly: `Python, FastAPI, OpenCV, YOLOv8n (Ultralytics), PyTorch (CPU), Supabase (Postgres + Storage), RTSP, MJPEG, vanilla JavaScript, HTML/CSS`.
