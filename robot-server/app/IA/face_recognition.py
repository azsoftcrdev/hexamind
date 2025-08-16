import cv2
import mediapipe as mp
from typing import Tuple, List

class FaceResult:
    def __init__(self, frame, faces: List[Tuple[int, int, int, int]]):
        self.frame = frame
        self.faces = faces

class FaceDetector:
    def __init__(self, detection_confidence: float = 0.6):
        self.mp_face = mp.solutions.face_detection
        self.face_detector = self.mp_face.FaceDetection(
            model_selection=0,
            min_detection_confidence=detection_confidence
        )

    def process_frame(self, frame_bgr, draw: bool = True) -> FaceResult:
        results = self.face_detector.process(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        faces = []

        if results.detections:
            for det in results.detections:
                bboxC = det.location_data.relative_bounding_box
                ih, iw, _ = frame_bgr.shape
                x = int(bboxC.xmin * iw)
                y = int(bboxC.ymin * ih)
                w = int(bboxC.width * iw)
                h = int(bboxC.height * ih)
                faces.append((x, y, w, h))

                if draw:
                    # Dibuja el recuadro
                    cv2.rectangle(frame_bgr, (x, y), (x + w, y + h), (0, 255, 0), 2)

                    # Persona detectada (arriba)
                    cv2.putText(frame_bgr, "Persona detectada", (x, y - 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                    # Confianza
                    confianza = int(det.score[0] * 100)
                    cv2.putText(frame_bgr, f"Confianza: {confianza}%", (x, y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        return FaceResult(frame_bgr, faces)
