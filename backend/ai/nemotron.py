"""Optional NVIDIA Nemotron analysis (never on the critical path).

Only invoked AFTER a SUSPICIOUS_ACTIVITY event, on that incident's
screenshot — never per-frame, never during live streaming. YOLO stays
the detector. Any failure (no key, network, model error) returns
ok=False so the incident is still stored normally in Supabase.

Stdlib only (urllib) — no new dependencies. The API key is read from
env at call time and never logged, returned, or included in errors.
"""
import base64
import json
import os
import urllib.request
from typing import Any, Optional

try:  # ensure .env is loaded even for standalone use
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
TIMEOUT_SEC = 120


def _creds() -> tuple[str, str]:
    return (os.getenv("NVIDIA_API_KEY", "").strip(),
            os.getenv("NVIDIA_MODEL", "").strip())


def analyze_image(image_jpeg: bytes, prompt: Optional[str] = None,
                  timeout: int = TIMEOUT_SEC) -> dict[str, Any]:
    """Send one JPEG to Nemotron, return {ok, text, model, error}.

    Never raises for API-level failures; raises only ValueError when
    called without image bytes (caller bug). Key never appears in output.
    """
    if not image_jpeg:
        raise ValueError("analyze_image needs JPEG bytes")
    api_key, model = _creds()
    if not api_key:
        return {"ok": False, "text": "", "model": model,
                "error": "NVIDIA_API_KEY missing — skipping AI analysis"}
    if not model:
        return {"ok": False, "text": "", "model": "",
                "error": "NVIDIA_MODEL missing — skipping AI analysis"}

    b64 = base64.b64encode(image_jpeg).decode("ascii")
    body = {"model": model,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt or (
                    "You are a security-camera assistant. Describe this frame "
                    "in 3-5 plain sentences: is a person present, what are "
                    "they doing, and is anything potentially suspicious? "
                    "Do not claim a crime occurred.")},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}],
            "max_tokens": 512,
            "temperature": 0.2}
    req = urllib.request.Request(
        NIM_URL, data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + api_key,
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except Exception as exc:  # noqa: BLE001 — failure-tolerant by design
        return {"ok": False, "text": "", "model": model,
                "error": f"NVIDIA request failed: {type(exc).__name__}"}
    try:
        text = payload["choices"][0]["message"]["content"].strip()
        if not text:
            raise KeyError("empty content")
        return {"ok": True, "text": text, "model": model, "error": ""}
    except (KeyError, IndexError, TypeError, AttributeError):
        return {"ok": False, "text": "", "model": model,
                "error": "unexpected NVIDIA response shape"}
