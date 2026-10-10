"""Central configuration. Env vars only — never hardcode secrets.

Supports component-based Tapo credentials (preferred):

    TAPO_USERNAME=...
    TAPO_PASSWORD=...   # '@' is URL-encoded to %40 automatically
    TAPO_IP=192.168.1.4
    TAPO_RTSP_PORT=554
    TAPO_STREAM=stream1

...or a full override via TAPO_RTSP_URL. Never logs the password.
"""
import os
from dataclasses import dataclass
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()  # loads .env if present; real values come from the user


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    tapo_rtsp_url: str = os.getenv("TAPO_RTSP_URL", "").strip()
    tapo_username: str = os.getenv("TAPO_USERNAME", "").strip()
    # TAPO_IP preferred; TAPO_CAMERA_IP kept as legacy alias.
    tapo_ip: str = os.getenv("TAPO_IP", os.getenv("TAPO_CAMERA_IP", "")).strip()
    tapo_rtsp_port: int = _int("TAPO_RTSP_PORT", 554)
    tapo_stream: str = os.getenv("TAPO_STREAM", "stream1").strip() or "stream1"

    camera_name: str = os.getenv("CAMERA_NAME", "Entrance Camera")
    camera_id: str = os.getenv("CAMERA_ID", "camera_01")

    stream_width: int = _int("STREAM_WIDTH", 640)
    stream_fps: int = _int("STREAM_FPS", 10)
    rtsp_timeout_seconds: int = _int("RTSP_TIMEOUT_SECONDS", 10)

    suspicious_duration_seconds: int = _int("SUSPICIOUS_DURATION_SECONDS", 10)

    pipeline_enabled: bool = os.getenv("PIPELINE_ENABLED", "1").strip() not in ("0", "false", "no")
    pipeline_sample_fps: float = float(os.getenv("PIPELINE_SAMPLE_FPS", "1.0") or 1.0)
    save_person_detected: bool = os.getenv("SAVE_PERSON_DETECTED", "1").strip() not in ("0", "false", "no")
    person_cooldown_sec: int = _int("PERSON_COOLDOWN_SEC", 120)

    supabase_url: str = os.getenv("SUPABASE_URL", "").strip()
    supabase_service_key: str = os.getenv("SUPABASE_SERVICE_KEY", "").strip()

    @property
    def tapo_password(self) -> str:
        return os.getenv("TAPO_PASSWORD", "")

    @property
    def rtsp_url_effective(self) -> str:
        """Full override wins; otherwise build from components.

        Password is percent-encoded so a literal '@' becomes %40 and
        does not break the userinfo@host split in the RTSP URL.
        """
        if self.tapo_rtsp_url:
            return self.tapo_rtsp_url
        if not (self.tapo_username and self.tapo_password and self.tapo_ip):
            return ""
        user = quote(self.tapo_username, safe="")
        pwd = quote(self.tapo_password, safe="")
        return (f"rtsp://{user}:{pwd}@{self.tapo_ip}:"
                f"{self.tapo_rtsp_port}/{self.tapo_stream}")


settings = Settings()


def mask_rtsp_url(url: str) -> str:
    """Hide password for logs/API responses."""
    if not url:
        return "not configured"
    try:
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            creds, host = rest.rsplit("@", 1)
            user = creds.split(":", 1)[0] if ":" in creds else creds
            return f"{scheme}://{user}:****@{host}"
        return f"{scheme}://****"
    except Exception:
        return "configured"
