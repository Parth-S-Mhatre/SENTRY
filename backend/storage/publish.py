"""Stage 6D — publish local evidence to Supabase.

Order (never lost evidence):
  1. upload screenshot.jpg -> evidence bucket, incidents/{id}/
  2. upload clip.mp4        -> same folder
  3. insert the `incidents` row with both Storage paths
  4. only then delete the local dir.

Any failure raises with local files preserved. EvidenceCapture,
detection, and rules are untouched — this consumes their outputs.
"""
import os
import shutil
from typing import Any

from backend.config import settings
from backend.storage.supabase_client import get_client

BUCKET = "evidence"

_col_cache: dict[str, bool] = {}


def table_has_column(column: str) -> bool:
    """Check once per process whether `incidents` has a column (e.g. a
    user-added ai_analysis). Never raises — unknown means absent."""
    if column not in _col_cache:
        try:
            rows = get_client().table("incidents").select("*").limit(1).execute().data
            _col_cache[column] = bool(rows) and column in rows[0]
        except Exception:  # noqa: BLE001
            _col_cache[column] = False
    return _col_cache[column]


def publish_screenshot_incident(incident_id: str, local_dir: str,
                                meta: dict[str, Any],
                                delete_local: bool = True) -> dict[str, Any]:
    """Screenshot-only incident (brief PERSON_DETECTED sighting, no clip).
    Same ordering guarantee: upload -> row -> delete local on success."""
    shot = os.path.join(local_dir, "screenshot.jpg")
    if not os.path.exists(shot):
        raise FileNotFoundError(f"screenshot missing in {local_dir}")
    shot_path = f"incidents/{incident_id}/screenshot.jpg"
    client = get_client()
    with open(shot, "rb") as fh:
        client.storage.from_(BUCKET).upload(
            shot_path, fh.read(), {"content-type": "image/jpeg"})
    row = {"camera_id": meta.get("camera_id", settings.camera_id),
           "camera_name": meta.get("camera_name", settings.camera_name),
           "event_type": meta.get("event_type", "PERSON_DETECTED"),
           "confidence": meta.get("confidence", 0.0),
           "description": meta.get("description", ""),
           "status": "NEW",
           "screenshot_path": shot_path,
           "clip_path": None}
    inserted = client.table("incidents").insert(row).execute().data
    if not inserted:
        raise RuntimeError("incidents insert returned no row; local evidence kept")
    if delete_local:
        shutil.rmtree(local_dir, ignore_errors=True)
    return {"dbId": inserted[0].get("id"), "screenshot_path": shot_path}


def publish_incident(incident_id: str, local_dir: str,
                     meta: dict[str, Any],
                     delete_local: bool = True) -> dict[str, Any]:
    shot = os.path.join(local_dir, "screenshot.jpg")
    clip = os.path.join(local_dir, "clip.mp4")
    if not os.path.exists(shot) or not os.path.exists(clip):
        raise FileNotFoundError(f"evidence incomplete in {local_dir}")

    shot_path = f"incidents/{incident_id}/screenshot.jpg"
    clip_path = f"incidents/{incident_id}/clip.mp4"
    client = get_client()

    with open(shot, "rb") as fh:
        client.storage.from_(BUCKET).upload(
            shot_path, fh.read(), {"content-type": "image/jpeg"})
    with open(clip, "rb") as fh:
        client.storage.from_(BUCKET).upload(
            clip_path, fh.read(), {"content-type": "video/mp4"})

    row = {"camera_id": meta.get("camera_id", settings.camera_id),
           "camera_name": meta.get("camera_name", settings.camera_name),
           "event_type": meta.get("event_type", "SUSPICIOUS_ACTIVITY"),
           "confidence": meta.get("confidence", 0.0),
           "description": meta.get("description", ""),
           "status": "NEW",
           "screenshot_path": shot_path,
           "clip_path": clip_path}
    inserted = client.table("incidents").insert(row).execute().data
    if not inserted:
        raise RuntimeError("incidents insert returned no row; local evidence kept")
    rid = inserted[0].get("id")

    _attach_ai_text(client, rid, meta.get("ai_analysis", ""))

    if delete_local:
        shutil.rmtree(local_dir, ignore_errors=True)
    return {"dbId": rid, "screenshot_path": shot_path,
            "clip_path": clip_path}


def _attach_ai_text(client: Any, row_id: str, text: str) -> None:
    """Best-effort: store Nemotron text if the column exists, else skip."""
    if not text or not table_has_column("ai_analysis"):
        return
    try:
        client.table("incidents").update(
            {"ai_analysis": text[:2000]}).eq("id", row_id).execute()
    except Exception:  # noqa: BLE001 — analysis is optional, never fatal
        pass
