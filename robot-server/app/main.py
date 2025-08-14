# app/main.py
from contextlib import asynccontextmanager
import asyncio, time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.bus import Bus
from .core.settings import HTTP_PORT
from .core.alerts import alerts_loop
from .sensors.camera import camera, get_telemetry_snapshot  # ajusta import si no moviste
from .web.routes_stream import router as stream_router
from .web.routes_status import router as status_router
from .web.routes_control import router as control_router
from .web import ws as ws_module

bus = Bus()
t0 = time.time()
_bg_tasks: list[asyncio.Task] = []

async def telemetry_loop():
    while True:
        await bus.publish("telemetry", get_telemetry_snapshot())
        await asyncio.sleep(0.2)

@asynccontextmanager
async def lifespan(app: FastAPI):
    ws_module.BUS = bus
    from .web import routes_status, routes_control
    routes_status.BUS = bus
    routes_control.BUS = bus

    # Abrir cámara
    try:
        camera.open()
        print("[INFO] Cámara abierta")
    except Exception as e:
        print("[WARN] No se pudo abrir la cámara:", e)

    # Tareas de fondo
    _bg_tasks.append(asyncio.create_task(telemetry_loop()))
    _bg_tasks.append(asyncio.create_task(alerts_loop(bus)))
    # (futuro) _bg_tasks.append(asyncio.create_task(lidar_loop(bus, driver)))
    # (futuro) _bg_tasks.append(asyncio.create_task(gps_loop(bus)))

    yield

    # Shutdown ordenado
    for t in _bg_tasks:
        t.cancel()
    try:
        camera.release()
    except Exception:
        pass

app = FastAPI(title="HexaMind Robot Server (Phase 1)", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(status_router, prefix="", tags=["status"])
app.include_router(stream_router, prefix="", tags=["stream"])
app.include_router(control_router, prefix="/control", tags=["control"])
app.mount("/ws", ws_module.ws_app)