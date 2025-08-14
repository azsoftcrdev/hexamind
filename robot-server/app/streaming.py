# app/streaming.py
import cv2, numpy as np, time
from .sensors.camera import camera
from .IA import ColorRecognizer
from .IA.face_recognition import FaceDetector 

BOUNDARY = b"--frame"
_recog = ColorRecognizer()
_face = FaceDetector()                                

def mjpeg_generator(mode: str | None = None,
                    color: str | None = None,
                    overlay: bool = True,
                    quality: int = 80):

    if mode == "color":
        _recog.set_current_color(color)

    while True:
        try:
            jpg = camera.snapshot_jpeg(quality=quality)

            if mode in ("color", "face"):
                # decodificar a BGR
                arr = np.frombuffer(jpg, dtype=np.uint8)
                frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if frame is None:
                    payload = jpg
                else:
                    if mode == "color":
                        res = _recog.process_frame(frame)
                        frame_out = res.frame if overlay else frame
                    else:  # mode == "face"
                        fres = _face.process_frame(frame, draw=overlay)
                        frame_out = fres.frame

                    ok, buf = cv2.imencode(".jpg", frame_out, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
                    payload = buf.tobytes() if ok else jpg
            else:
                payload = jpg

            yield (BOUNDARY +
                   b"\r\nContent-Type: image/jpeg\r\nContent-Length: " +
                   str(len(payload)).encode() + b"\r\n\r\n" + payload + b"\r\n")

        except Exception:
            time.sleep(0.03)
            continue