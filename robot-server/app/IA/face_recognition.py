import cv2
import mediapipe as mp
from typing import Tuple, List

class FaceResult:
    def __init__(self, frame, faces: List[Tuple[int, int, int, int]]):
        self.frame = frame
        self.faces = faces

class FaceDetector:
    def __init__(self, detection_confidence: float = 0.6, max_side: int = 640):
        """
        detection_confidence: umbral de confianza MediaPipe
        max_side: redimensiona el frame para detección (lado mayor <= max_side)
        """
        self.mp_face = mp.solutions.face_detection
        self.face_detector = self.mp_face.FaceDetection(
            model_selection=0,
            min_detection_confidence=detection_confidence
        )
        self.max_side = int(max_side) if max_side and max_side > 0 else 640

        self._font = cv2.FONT_HERSHEY_SIMPLEX
        self._color = (0, 255, 0)

    def _resize_for_detection(self, frame_bgr):
        h, w = frame_bgr.shape[:2]
        scale = 1.0
        if max(h, w) > self.max_side:
            scale = self.max_side / float(max(h, w))
            new_w = int(w * scale)
            new_h = int(h * scale)
            small = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
            return small, scale
        return frame_bgr, 1.0

    def _clip_bbox(self, x, y, w, h, W, H):
        x = max(0, min(x, W - 1))
        y = max(0, min(y, H - 1))
        w = max(0, min(w, W - x))
        h = max(0, min(h, H - y))
        return x, y, w, h

    def process_frame(self, frame_bgr, draw: bool = True) -> FaceResult:
        small_bgr, scale = self._resize_for_detection(frame_bgr)
        small_rgb = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2RGB)

        results = self.face_detector.process(small_rgb)
        faces: List[Tuple[int, int, int, int]] = []

        if results and results.detections:
            H, W = frame_bgr.shape[:2]
            inv = 1.0 / scale 

            for det in results.detections:
                bboxC = det.location_data.relative_bounding_box
            
                x_s = bboxC.xmin * small_bgr.shape[1]
                y_s = bboxC.ymin * small_bgr.shape[0]
                w_s = bboxC.width * small_bgr.shape[1]
                h_s = bboxC.height * small_bgr.shape[0]
          
                x = int(x_s * inv)
                y = int(y_s * inv)
                w = int(w_s * inv)
                h = int(h_s * inv)

                x, y, w, h = self._clip_bbox(x, y, w, h, W, H)
                faces.append((x, y, w, h))

                if draw:
                    cv2.rectangle(frame_bgr, (x, y), (x + w, y + h), self._color, 2)

                    confianza = int(det.score[0] * 100) if det.score else 0
                    y_text = max(0, y - 10)
                    label = f"Persona detectada  |  Confianza: {confianza}%"
                    cv2.putText(frame_bgr, label, (x, y_text),
                                self._font, 0.55, self._color, 2, cv2.LINE_AA)

        return FaceResult(frame_bgr, faces)