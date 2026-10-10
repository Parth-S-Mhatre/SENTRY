"""Read-side Supabase access for the API layer.

Separation: publish.py writes, this module reads. Lists incidents
(newest first), fetches one row, and mints short-lived signed URLs for
the private evidence bucket — the service key never leaves the backend.
"""
from typing import Any, Optional

from backend.storage.publish import BUCKET
from backend.storage.supabase_client import get_client

SIGNED_URL_TTL_SEC = 300
MAX_LIMIT = 100


def list_incidents(limit: int = 20) -> list[dict[str, Any]]:
    client = get_client()
    res = (client.table("incidents").select("*")
           .order("created_at", desc=True).limit(limit).execute())
    return res.data or []


def get_incident(incident_id: str) -> Optional[dict[str, Any]]:
    client = get_client()
    res = (client.table("incidents").select("*")
           .eq("id", incident_id).limit(1).execute())
    rows = res.data or []
    return rows[0] if rows else None


def signed_url(storage_path: str,
               expires_in: int = SIGNED_URL_TTL_SEC) -> Optional[str]:
    """Short-lived download URL for a private-bucket object, else None."""
    if not storage_path:
        return None
    client = get_client()
    res = client.storage.from_(BUCKET).create_signed_url(storage_path,
                                                         expires_in)
    url = (res or {}).get("signedURL") if isinstance(res, dict) else None
    if url and url.startswith("/"):
        from backend.config import settings
        url = settings.supabase_url.rstrip("/") + "/storage/v1" + url
    return url
