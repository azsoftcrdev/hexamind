import time
from .camera import camera

BOUNDARY = b"--frame"

def mjpeg_generator():
    while True:
        try:
            jpg = camera.snapshot_jpeg(quality=80)
            yield (
                BOUNDARY
                + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                + str(len(jpg)).encode()
                + b"\r\n\r\n"
                + jpg
                + b"\r\n"
            )
        except Exception:
            # Si por un instante no se pudo leer/codificar, no rompas el stream
            import time; time.sleep(0.03)
            continue