# app/detections/face_recognition.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional

import cv2
import numpy as np

@dataclass
class FaceResult:
    frame: np.ndarray
    boxes: List[Tuple[int, int, int, int]]  # (x, y, w, h)

class FaceDetector:
    def __init__(
        self,
        cascade_path: Optional[str] = None,
        scale_factor: float = 1.3,
        min_neighbors: int = 5,
        min_size: Tuple[int, int] = (30, 30),
    ) -> None:
        if cascade_path is None:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        if self.face_cascade.empty():
            raise RuntimeError(f"No se pudo cargar el cascade en: {cascade_path}")

        self.scale_factor = scale_factor
        self.min_neighbors = min_neighbors
        self.min_size = min_size

    def process_frame(self, frame_bgr: np.ndarray, draw: bool = True) -> FaceResult:
        frame = frame_bgr.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=self.scale_factor,
            minNeighbors=self.min_neighbors,
            minSize=self.min_size,
        )

        boxes: List[Tuple[int, int, int, int]] = []
        for (x, y, w, h) in faces:
            boxes.append((x, y, w, h))
            if draw:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(
                    frame, "Person", (x, max(25, y - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
                )

        return FaceResult(frame=frame, boxes=boxes)
