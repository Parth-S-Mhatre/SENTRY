"""Stage 4 — simple, explainable suspicious-activity rules.

MVP rule (the only one for now):

    IF a person is continuously present inside the configured area
       for longer than SUSPICIOUS_DURATION_SECONDS
    THEN emit SUSPICIOUS_ACTIVITY ("Potential Suspicious Activity")

A rising edge (person appears) emits PERSON_DETECTED. Each continuous
presence episode fires at most one SUSPICIOUS_ACTIVITY; absence resets
the timer. New rules later just implement update() and are added to
RuleEngine — nothing else changes.

Terminology: the engine never claims "theft". The admin reviews evidence.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from backend.detection.detector import Detection

AREA_FULL = (0.0, 0.0, 1.0, 1.0)  # whole frame (fractions of width/height)


def _center_in_area(bbox: tuple[int, int, int, int],
                    frame_size: tuple[int, int],
                    area: tuple[float, float, float, float]) -> bool:
    x1, y1, x2, y2 = bbox
    fw, fh = frame_size
    if fw <= 0 or fh <= 0:
        return True
    cx, cy = ((x1 + x2) / 2 / fw), ((y1 + y2) / 2 / fh)
    ax1, ay1, ax2, ay2 = area
    return ax1 <= cx <= ax2 and ay1 <= cy <= ay2


@dataclass
class Event:
    event_type: str  # PERSON_DETECTED | SUSPICIOUS_ACTIVITY
    timestamp: float
    confidence: float
    description: str
    duration_sec: float = 0.0
    status: str = "NEW"

    def as_dict(self) -> dict[str, Any]:
        return {"eventType": self.event_type,
                "timestamp": self.timestamp,
                "confidence": round(self.confidence, 2),
                "description": self.description,
                "durationSec": round(self.duration_sec, 1),
                "status": self.status}


class PresenceRule:
    """Continuous-presence rule. All timing uses the caller's clock so tests
    can drive it with simulated timestamps (deterministic, no sleeps)."""

    def __init__(self, duration_threshold_sec: float = 10.0,
                 area: tuple[float, float, float, float] = AREA_FULL,
                 max_gap_sec: float = 3.0) -> None:
        self.threshold = duration_threshold_sec
        self.area = area
        self.max_gap = max_gap_sec
        self._episode_start: Optional[float] = None
        self._last_seen: Optional[float] = None
        self._fired_this_episode = False
        self._peak_conf = 0.0

    def reset(self) -> None:
        self._episode_start = None
        self._last_seen = None
        self._fired_this_episode = False
        self._peak_conf = 0.0

    def update(self, now: float, detections: list[Detection],
               frame_size: tuple[int, int] = (0, 0)) -> list[Event]:
        events: list[Event] = []
        present = [d for d in detections
                   if _center_in_area(d.bbox, frame_size, self.area)]
        if not present:
            # Absence ends the episode (timer resets).
            self.reset()
            return events

        conf = max(d.confidence for d in present)
        self._peak_conf = max(self._peak_conf, conf)
        if self._episode_start is None:
            # Rising edge: person appeared.
            self._episode_start = now
            self._last_seen = now
            events.append(Event("PERSON_DETECTED", now, conf,
                                "Person detected in monitored area"))
            return events

        # Gap tolerance: brief detector misses don't reset the episode.
        assert self._last_seen is not None
        if now - self._last_seen > self.max_gap:
            self.reset()
            self._episode_start = now
            events.append(Event("PERSON_DETECTED", now, conf,
                                "Person detected in monitored area"))
            self._last_seen = now
            return events

        self._last_seen = now
        duration = now - self._episode_start
        if duration >= self.threshold and not self._fired_this_episode:
            self._fired_this_episode = True
            events.append(Event(
                "SUSPICIOUS_ACTIVITY", now, self._peak_conf,
                f"Potential suspicious activity: person continuously present "
                f"for {duration:.0f}s (threshold {self.threshold:.0f}s)",
                duration_sec=duration))
        return events


class RuleEngine:
    """Holds the active rules. Later rules are appended, never rewritten."""

    def __init__(self, duration_threshold_sec: float = 10.0,
                 area: tuple[float, float, float, float] = AREA_FULL) -> None:
        self.rules = [PresenceRule(duration_threshold_sec, area)]

    def update(self, detections: list[Detection],
               frame_size: tuple[int, int] = (0, 0),
               now: Optional[float] = None) -> list[Event]:
        now = time.time() if now is None else now
        events: list[Event] = []
        for rule in self.rules:
            events.extend(rule.update(now, detections, frame_size))
        return events
