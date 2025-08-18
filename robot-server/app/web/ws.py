# app/web/ws.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio, time
from typing import Optional
from ..core.bus import Bus
from ..core.settings import WS_RATE_HZ
from ..motion.controller_vel import MotionControllerVel

ws_app = FastAPI()
BUS: Optional[Bus] = None

# Singleton perezoso del controlador (por si el lifespan no lo inyecta)
_controller: Optional[MotionControllerVel] = None
def ctl() -> MotionControllerVel:
    import asyncio
    global _controller
    if _controller is None:
        _controller = MotionControllerVel(hz=15.0, deadman_s=0.8)
        _controller.start(asyncio.get_event_loop())
    return _controller

@ws_app.websocket("/")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    if BUS is None:
        await ws.close()
        return

    sub = BUS.subscribe(["telemetry", "alert", "mode", "ui_event"]) 

    send_interval = 1.0 / max(WS_RATE_HZ, 0.1) 
    last_send = 0.0
    last_msgs = {}

    IN_HZ = 30.0
    min_recv_dt = 1.0 / IN_HZ
    last_recv_ts = 0.0

    try:
        while True:
            recv_task = asyncio.create_task(ws.receive_json())
            bus_task  = asyncio.create_task(sub.get())

            done, pending = await asyncio.wait(
                {recv_task, bus_task},
                return_when=asyncio.FIRST_COMPLETED,
                timeout=send_interval
            )

            now = time.time()

            # ───── Mensaje desde el cliente ─────
            if recv_task in done:
                try:
                    msg = recv_task.result()  # dict
                except Exception:
                    # cliente envió algo no-JSON o cerró abruptamente
                    for p in pending: p.cancel()
                    break

                # Rate limit suave de entrada
                if (now - last_recv_ts) >= min_recv_dt:
                    last_recv_ts = now
                    # Contrato: { type: "motion_setpoint", x, y, z, speed? }
                    mtype = msg.get("type") or msg.get("topic")
                    if mtype == "motion_setpoint":
                        try:
                            x = int(msg.get("x", 0))
                            y = int(msg.get("y", 0))
                            z = int(msg.get("z", 0))
                            speed = msg.get("speed", None)
                            speed = int(speed) if speed is not None else None
                            # Actualiza setpoint (latest-wins). El bucle del controlador se encarga del move()
                            ctl().set_vel(x, y, z, speed)
                            # (opcional) mandar ACK local al cliente
                            await ws.send_json({"topic": "motion/ack", "data": {"x": x, "y": y, "z": z, "speed": speed}})
                        except Exception:
                            # Ignora valores inválidos
                            pass
                    else:
                        topic = msg.get("topic")
                        data  = msg.get("data")
                        if topic and (data is not None):
                            await BUS.publish(topic, data)

            # ───── Mensaje desde el BUS (para enviar a cliente) ─────
            if bus_task in done:
                try:
                    topic, data = bus_task.result()
                    last_msgs[topic] = data  # coalescing: se queda el último por tópico
                except Exception:
                    pass

            # ───── Flush hacia el cliente, coalesced + throttled ─────
            if (now - last_send) >= send_interval and last_msgs:
                try:
                    # envía cada tópico y vacía
                    for topic, data in list(last_msgs.items()):
                        await ws.send_json({"topic": topic, "data": data})
                    last_msgs.clear()
                    last_send = now
                except Exception:
                    # cliente desconectado
                    for p in pending: p.cancel()
                    break

            # Limpieza de tareas pendientes
            for p in pending: 
                p.cancel()

    except WebSocketDisconnect:
        pass
    finally:
        sub.close()
