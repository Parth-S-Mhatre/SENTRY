"""Stage 3 — pretrained person detection (YOLOv8n, COCO class 0 = person).

Design notes:
- Model loads once, lazily, on first detect() — import stays cheap and a
  model failure never breaks the camera pipeline (caller catches).
- Inference runs on a downscaled copy (default 640px wide) for CPU speed;
  boxes are scaled back to full-frame coordinates for drawing/saving.
- Only PERSON is reported. Confidence threshold is configurable.
- No tracking, no rules, no uploads here — later stages consume detect().
"""
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

PERSON_CLASS_ID = 0
DEFAULT_MODEL = "yolov8n.pt"  # tiny, CPU-friendly; auto-downloaded on first use
DEFAULT_PROC_WIDTH = 640


@dataclass
class Detection:
    label: str = "Person"
    confidence: float = 0.0
    # bbox in FULL-frame pixels: x1, y1, x2, y2
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)

    def as_dict(self) -> dict[str, Any]:
        x1, y1, x2, y2 = self.bbox
        return {"label": self.label, "confidence": round(self.confidence, 2),
                "bbox": [x1, y1, x2, y2]}


class PersonDetector:
    def __init__(self, model: str = DEFAULT_MODEL,
                 proc_width: int = DEFAULT_PROC_WIDTH,
                 min_confidence: float = 0.5) -> None:
        self._model_name = model
        self._proc_width = proc_width
        self._min_conf = min_confidence
        self._model: Any = None
        self._frames_seen = 0
        self._person_frames = 0

    def _load(self) -> None:
        if self._model is None:
            from ultralytics import YOLO
            self._model = YOLO(self._model_name)

    @property
    def stats(self) -> dict[str, int]:
        return {"framesSeen": self._frames_seen,
                "personFrames": self._person_frames}

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Detect people. Never raises on empty input; model errors propagate
        to the caller so the pipeline can log them without crashing."""
        self._frames_seen += 1
        if frame is None or frame.size == 0:
            return []
        self._load()

        h, w = frame.shape[:2]
        scale = self._proc_width / w if w > self._proc_width else 1.0
        small = cv2.resize(frame, (int(w * scale), int(h * scale))) \
            if scale < 1.0 else frame

        results = self._model.predict(small, verbose=False)
        out: list[Detection] = []
        for box in results[0].boxes:
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            if cls != PERSON_CLASS_ID or conf < self._min_conf:
                continue
            x1, y1, x2, y2 = (np.array(box.xyxy[0].cpu()) / scale).astype(int)
            out.append(Detection(confidence=conf,
                                 bbox=(int(x1), int(y1), int(x2), int(y2))))
        if out:
            self._person_frames += 1
        return out


def draw_boxes(frame: np.ndarray, detections: list[Detection]) -> np.ndarray:
    """Return a copy with person boxes + 'Person 0.91' labels drawn."""
    annotated = frame.copy()
    for d in detections:
        x1, y1, x2, y2 = d.bbox
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 200, 0), 2)
        label = f"Person {d.confidence:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(annotated, (x1, y1 - th - 8), (x1 + tw + 6, y1), (0, 200, 0), -1)
        cv2.putText(annotated, label, (x1 + 3, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return annotated
