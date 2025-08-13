import os, time
from typing import Optional, Tuple, Union
import cv2
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "config", ".env"))

def _parse_device(dev: str) -> Union[int, str]:
    # En Windows normalmente "0"; en Linux puede ser "/dev/video0"
    try:
        return int(dev)
    except (TypeError, ValueError):
        return dev or 0

class Camera:
    def __init__(self):
        self.device = _parse_device(os.getenv("CAMERA_DEVICE", "0"))
        self.width  = int(os.getenv("CAMERA_WIDTH", "640"))
        self.height = int(os.getenv("CAMERA_HEIGHT", "480"))
        self.fps    = int(os.getenv("CAMERA_FPS", "30"))
        self.codec  = os.getenv("CAMERA_CODEC", "MJPG").strip().upper()
        self._cap: Optional[cv2.VideoCapture] = None
        self._last_frame = None
        self._t_last = time.time()
        self._fps_actual = 0.0

    def open(self):
        if self._cap is not None:
            return
        self._cap = cv2.VideoCapture(self.device)
        # Resolución y FPS
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS,          self.fps)
        # Codec MJPG (si está disponible)
        if self.codec == "MJPG":
            fourcc = cv2.VideoWriter_fourcc(*"MJPG")
            self._cap.set(cv2.CAP_PROP_FOURCC, fourcc)

        if not self._cap.isOpened():
            raise RuntimeError(f"No se pudo abrir la cámara: {self.device}")

    def read(self):
        if self._cap is None:
            self.open()
        ok, frame = self._cap.read()
        if not ok:
            raise RuntimeError("No se pudo leer frame de la cámara")
        # Calcular FPS real
        t = time.time()
        dt = max(t - self._t_last, 1e-6)
        self._fps_actual = 1.0 / dt
        self._t_last = t
        self._last_frame = frame
        return frame

    def get_fps_actual(self) -> float:
        return float(self._fps_actual)

    def get_resolution(self) -> Tuple[int, int]:
        return (self.width, self.height)

    def snapshot_jpeg(self, quality: int = 85) -> bytes:
        frame = self.read()
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise RuntimeError("No se pudo codificar JPG")
        return buf.tobytes()

    def release(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None

# Instancia global para reusar la cámara
camera = Camera()
