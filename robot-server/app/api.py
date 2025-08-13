import os, time
from fastapi import FastAPI, Response
from fastapi.responses import PlainTextResponse
from .camera import camera
from .streaming import mjpeg_generator, BOUNDARY
from fastapi.responses import StreamingResponse

app = FastAPI(title="HexaMind Robot Server (Phase 1)")
t0 = time.time()

@app.on_event("startup")
def _on_startup():
    # Abrimos la cámara al iniciar (también se abre lazy en Camera.read)
    try:
        camera.open()
    except Exception as e:
        # No lanzamos 500 aquí para que /health responda con error claro
        print("[WARN] No se pudo abrir la cámara en startup:", e)

@app.on_event("shutdown")
def _on_shutdown():
    camera.release()

@app.get("/health")
def health():
    up = time.time() - t0
    w, h = camera.get_resolution()
    return {
        "ok": True,
        "uptime_sec": round(up, 1),
        "resolution": [w, h],
        "fps_current": round(camera.get_fps_actual(), 2),
    }

@app.get("/snapshot.jpg")
def snapshot_jpg():
    jpg = camera.snapshot_jpeg(quality=85)
    return Response(content=jpg, media_type="image/jpeg")

@app.get("/stream.mjpg")
def stream_mjpg():
    headers = {
        "Age": "0",
        "Cache-Control": "no-cache, private",
        "Pragma": "no-cache",
        "Content-Type": "multipart/x-mixed-replace; boundary=frame",
    }
    return StreamingResponse(mjpeg_generator(),
                             media_type="multipart/x-mixed-replace; boundary=frame",
                             headers=headers)
