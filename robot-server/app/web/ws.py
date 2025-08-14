# app/web/ws.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
from ..core.bus import Bus

ws_app = FastAPI()
BUS: Bus | None = None

@ws_app.on_event("startup")
async def _ws_startup():
    if BUS is None:
        print("[WS] Bus no inyectado aún (main debe asignarlo)")

@ws_app.websocket("/")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    sub = BUS.subscribe(["telemetry", "alert"]) if BUS else None
    try:
        while True:
            # recibir (control remoto, etc.)
            recv_task = asyncio.create_task(ws.receive_json())
            # publicar desde el bus
            bus_task = asyncio.create_task(sub.get()) if sub else None

            done, pending = await asyncio.wait(
                {t for t in [recv_task, bus_task] if t},
                return_when=asyncio.FIRST_COMPLETED,
                timeout=1.0
            )

            if recv_task in done:
                try:
                    msg = recv_task.result()
                    if BUS and "topic" in msg:
                        await BUS.publish(msg["topic"], msg.get("data"))
                except Exception:
                    pass

            if bus_task and (bus_task in done):
                topic, data = bus_task.result()
                await ws.send_json({"topic": topic, "data": data})

            for p in pending:
                p.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        if sub:
            sub.close()
