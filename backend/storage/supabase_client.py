"""Supabase client init (Stage 6 connection test).

Only creates the client from env config. Uploads / DB writes belong to
the later evidence-pipeline step — nothing here touches Storage data.
The service key never leaves this module (never logged or returned).
"""
from typing import Any, Optional

from backend.config import settings

_client: Optional[Any] = None


def get_client() -> Any:
    """Return the shared Supabase client. Raises with a non-secret message
    when configuration is missing."""
    global _client
    if _client is not None:
        return _client
    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL is missing in .env")
    if not settings.supabase_service_key:
        raise RuntimeError("SUPABASE_SERVICE_KEY is missing in .env")
    from supabase import create_client
    _client = create_client(settings.supabase_url,
                            settings.supabase_service_key)
    return _client


def reset_client() -> None:
    """Test helper: drop the cached client."""
    global _client
    _client = None
