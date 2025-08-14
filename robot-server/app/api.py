# app/main.py (o donde tengas tu servidor)
import time
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from .camera import camera
from .streaming import mjpeg_generator  # BOUNDARY no se usa aquí
from fastapi import HTTPException

app = FastAPI(title="HexaMind Robot Server (Phase 1)")
t0 = time.time()

@app.on_event("startup")
def _on_startup():
    try:
        camera.open()
    except Exception as e:
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
def snapshot_jpg(quality: int = 85):
    jpg = camera.snapshot_jpeg(quality=quality)
    return Response(content=jpg, media_type="image/jpeg")

from fastapi import HTTPException

@app.get("/stream.mjpg")
def stream_mjpg(
    request: Request,
    mode: str | None = None,      # None | "color" | "face"
    color: str | None = None,     # "red"|"green"|"blue"|"yellow" (si mode=color)
    overlay: bool = True,
    quality: int = 80
):
    """
    Ejemplos:
    - /stream.mjpg
    - /stream.mjpg?mode=color               -> detección automática (ROI central)
    - /stream.mjpg?mode=color&color=red     -> evaluar solo rojo
    - /stream.mjpg?mode=face                -> detección de rostros (Haar)
    - /stream.mjpg?mode=color&overlay=false -> sin dibujo (pero sigue detectando)
    - /stream.mjpg?mode=color&quality=85    -> calidad JPEG
    """
    # Normaliza y valida modo
    if mode is not None:
        mode = mode.lower()
        if mode not in ("color", "face"):
            raise HTTPException(status_code=400, detail="mode debe ser 'color' o 'face'")

    # Valida color si corresponde
    if color is not None:
        color = color.lower()
        valid_colors = {"red", "green", "blue", "yellow"}
        if color not in valid_colors:
            raise HTTPException(status_code=400, detail=f"color inválido. Usa {sorted(valid_colors)}")
        if mode != "color":
            raise HTTPException(status_code=400, detail="param 'color' solo aplica con mode=color")

    # Limita calidad
    if not (10 <= quality <= 95):
        raise HTTPException(status_code=400, detail="quality debe estar entre 10 y 95")

    gen = mjpeg_generator(mode=mode, color=color, overlay=overlay, quality=quality)
    return StreamingResponse(gen, media_type="multipart/x-mixed-replace; boundary=frame")
