# app/sensors/camera.py
import os, time
from typing import Optional, Tuple, Union
from pathlib import Path
import numpy as np
import cv2
from dotenv import load_dotenv

# ---------- Carga .env desde robot-server/config/.env ----------
ENV_PATH = Path(__file__).resolve().parents[2] / "config" / ".env"
load_dotenv(ENV_PATH)

def _parse_device(dev: str) -> Union[int, str]:
    try:
        return int(dev)
    except (TypeError, ValueError):
        return dev or 0

# Reutilizamos objetos costosos (CLAHE) y evitamos trabajo si no hay baja luz
_CLAHE = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

def _lowlight_enhance(bgr: np.ndarray) -> np.ndarray:
    # Denoise ligero (más compacto y sin copias temporales innecesarias)
    den = cv2.fastNlMeansDenoisingColored(bgr, None, 5, 5, 7, 21)

    # Equalización adaptativa en luminancia (LAB)
    lab = cv2.cvtColor(den, cv2.COLOR_BGR2LAB)
    L, A, B = cv2.split(lab)
    L2 = _CLAHE.apply(L)
    lab[:, :, 0] = L2  # evita merge extra
    out = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    return out

class _EMA:
    """Suavizado temporal de frames; usa accumulateWeighted de OpenCV para velocidad."""
    def __init__(self, alpha: float = 0.2):
        self.alpha = float(alpha)
        self.acc: Optional[np.ndarray] = None

    def apply(self, frame: np.ndarray) -> np.ndarray:
        f32 = frame.astype(np.float32, copy=False)
        if self.acc is None:
            self.acc = f32.copy()
        else:
            cv2.accumulateWeighted(f32, self.acc, self.alpha)
        return np.clip(self.acc, 0, 255).astype(np.uint8, copy=False)

# ---------- Backend Astra opcional ----------
_ASTRA_OK = False
try:
    from pyorbbecsdk import Pipeline, Config, OBStreamType, OBFormat, OBAlignMode
    _ASTRA_OK = True
except Exception:
    _ASTRA_OK = False

class _Astra:
    """Backend para Orbbec Astra Pro (RGB + Depth). Devuelve depth en mm."""
    def __init__(self):
        if not _ASTRA_OK:
            raise RuntimeError("pyorbbecsdk no disponible")
        self.pipe = Pipeline()
        cfg = Config()
        w = int(os.getenv("CAMERA_WIDTH", "640"))
        h = int(os.getenv("CAMERA_HEIGHT", "480"))
        fps = int(os.getenv("CAMERA_FPS", "30"))
        cfg.enable_stream(OBStreamType.COLOR, w, h, OBFormat.RGB, fps)
        cfg.enable_stream(OBStreamType.DEPTH, w, h, OBFormat.Y16, fps)
        cfg.set_align_mode(OBAlignMode.ALIGN_D2C)  # alinea profundidad a color
        self.pipe.start(cfg)
        self._last_color: Optional[np.ndarray] = None
        self._last_depth_mm: Optional[np.ndarray] = None

    def read(self) -> np.ndarray:
        frames = self.pipe.wait_for_frames(1000)
        d = frames.get_depth_frame()
        c = frames.get_color_frame()
        if not d or not c:
            raise RuntimeError("Astra: no frame")

        # Evita copias intermedias usando frombuffer y reshape sin copiar
        color = np.frombuffer(c.get_data(), dtype=np.uint8)
        color = color.reshape(c.get_height(), c.get_width(), 3)
        depth = np.frombuffer(d.get_data(), dtype=np.uint16)
        depth = depth.reshape(d.get_height(), d.get_width())

        # SDK entrega color en RGB → conviértelo a BGR para OpenCV
        bgr = cv2.cvtColor(color, cv2.COLOR_RGB2BGR)
        self._last_color = bgr
        self._last_depth_mm = depth
        return bgr

    def depth_min_m(self) -> Optional[float]:
        if self._last_depth_mm is None:
            return None
        h, w = self._last_depth_mm.shape
        roi = self._last_depth_mm[h // 3 : 2 * h // 3, w // 3 : 2 * w // 3]
        # Filtra invalidos y distancia útil (< 8m)
        valid = roi[(roi > 0) & (roi < 8000)]
        return float(valid.min()) / 1000.0 if valid.size else None

    def depth_colormap_bgr(self) -> Optional[np.ndarray]:
        if self._last_depth_mm is None:
            return None
        # Escala simple 0..~8m → 0..255
        d8 = np.clip(self._last_depth_mm >> 3, 0, 255).astype(np.uint8, copy=False)
        return cv2.applyColorMap(d8, cv2.COLORMAP_JET)

    def release(self):
        try:
            self.pipe.stop()
        except Exception:
            pass

# ---------- Backend OpenCV clásico ----------
class _OpenCVCam:
    def __init__(self, device, width, height, fps, codec):
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self.codec = codec
        self._cap: Optional[cv2.VideoCapture] = None

    def open(self):
        if self._cap is not None:
            return
        self._cap = cv2.VideoCapture(self.device)

        # Intenta bajar el buffer interno para reducir latencia
        try:
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)
        if self.codec == "MJPG":
            fourcc = cv2.VideoWriter_fourcc(*"MJPG")
            self._cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        if not self._cap.isOpened():
            raise RuntimeError(f"No se pudo abrir la cámara: {self.device}")

        # Descarta un par de frames iniciales para estabilizar exposición/ganancia
        for _ in range(2):
            self._cap.read()

    def read(self) -> np.ndarray:
        if self._cap is None:
            self.open()
        ok, frame = self._cap.read()
        if not ok:
            raise RuntimeError("No se pudo leer frame de la cámara")
        return frame

    def release(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None

# ---------- Interfaz pública (compatible con tu código) ----------
class Camera:
    def __init__(self):
        # Fija hilos de OpenCV si la build lo soporta (evita sobre-subscription)
        try:
            cv2.setNumThreads(max(1, int(os.getenv("OPENCV_THREADS", "1"))))
        except Exception:
            pass

        self.backend = os.getenv("CAMERA_BACKEND", "opencv").strip().lower()  # "opencv" | "astra"
        self.device  = _parse_device(os.getenv("CAMERA_DEVICE", "0"))
        self.width   = int(os.getenv("CAMERA_WIDTH", "640"))
        self.height  = int(os.getenv("CAMERA_HEIGHT", "480"))
        self.fps     = int(os.getenv("CAMERA_FPS", "30"))
        self.codec   = os.getenv("CAMERA_CODEC", "MJPG").strip().upper()

        self.lowlight_auto   = os.getenv("CAMERA_LOWLIGHT_AUTO", "1") == "1"
        self.lowlight_force  = os.getenv("CAMERA_LOWLIGHT_FORCE", "0") == "1"
        self.lowlight_thresh = float(os.getenv("CAMERA_LOWLIGHT_THRESH", "30.0"))  # luminancia media 0..255

        self._ema = _EMA(alpha=float(os.getenv("CAMERA_TEMPORAL_EMA", "0.2")))
        self._fps_actual = 0.0
        self._t_last = time.time()
        self._last_frame: Optional[np.ndarray] = None

        # backends
        self._astra: Optional[_Astra] = None
        self._cv: Optional[_OpenCVCam] = None

    def open(self):
        if self.backend == "astra":
            if not _ASTRA_OK:
                raise RuntimeError("CAMERA_BACKEND=astra pero pyorbbecsdk no está instalado")
            if self._astra is None:
                self._astra = _Astra()
        else:
            if self._cv is None:
                self._cv = _OpenCVCam(self.device, self.width, self.height, self.fps, self.codec)
            self._cv.open()

    def _postprocess_lowlight(self, frame: np.ndarray) -> np.ndarray:
        # Detección eficiente de baja luz: evitamos denoise/CLAHE si no hace falta
        do_enh = self.lowlight_force
        if self.lowlight_auto and not do_enh:
            # usa mean sobre canal Y aproximado vía conversión rápida a escala de grises
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            do_enh = float(gray.mean()) < self.lowlight_thresh

        if do_enh:
            frame = _lowlight_enhance(frame)
            frame = self._ema.apply(frame)
        return frame

    def read(self) -> np.ndarray:
        if (self.backend == "astra" and self._astra is None) or (self.backend != "astra" and self._cv is None):
            self.open()

        frame = self._astra.read() if self.backend == "astra" else self._cv.read()
        frame = self._postprocess_lowlight(frame)

        t = time.time()
        dt = t - self._t_last
        if dt <= 0:
            dt = 1e-6
        self._fps_actual = 1.0 / dt
        self._t_last = t
        self._last_frame = frame
        return frame

    # -------- profundidad (solo cuando backend=astra) --------
    def depth_min_m(self) -> Optional[float]:
        if self.backend != "astra" or self._astra is None:
            return None
        return self._astra.depth_min_m()

    def depth_colormap_bgr(self) -> Optional[np.ndarray]:
        if self.backend != "astra" or self._astra is None:
            return None
        return self._astra.depth_colormap_bgr()

    # -------- API existente --------
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

    def snapshot_depth_jpeg(self) -> Optional[bytes]:
        """Devuelve JPEG del mapa de profundidad coloreado (solo Astra)."""
        vis = self.depth_colormap_bgr()
        if vis is None:
            return None
        ok, buf = cv2.imencode(".jpg", vis, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            return None
        return buf.tobytes()

    def release(self):
        if self._astra is not None:
            self._astra.release()
            self._astra = None
        if self._cv is not None:
            self._cv.release()
            self._cv = None

    def get_telemetry_snapshot(self) -> dict:
        try:
            w, h = self.get_resolution()
        except Exception:
            w, h = 0, 0
        try:
            fps = float(self.get_fps_actual())
        except Exception:
            fps = 0.0
        dmin = None
        if self.backend == "astra" and self._astra is not None:
            try:
                dmin = self.depth_min_m()
            except Exception:
                dmin = None
        return {
            "fps": round(fps, 2),
            "resolution": [w, h],
            "backend": self.backend,
            "depth_min_m": round(dmin, 3) if dmin is not None else None,
            "ts": time.time(),
        }

# ---------- Instancia global y helper conservados ----------
camera = Camera()

def get_telemetry_snapshot() -> dict:
    return camera.get_telemetry_snapshot()
