from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio, time
from ..core.bus import Bus
from ..core.settings import WS_RATE_HZ
from typing import Optional

ws_app = FastAPI()

BUS: Optional[Bus] = None


@ws_app.websocket("/")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    if BUS is None:
        await ws.close()
        return

    sub = BUS.subscribe(["telemetry", "alert", "mode"])  # agrega más temas si quieres
    send_interval = 1.0 / max(WS_RATE_HZ, 0.1)           # periodo mínimo entre envíos
    last_send = 0.0

    # buffers “coalesced”: guardamos solo el último por tema
    last_msgs = {}

    try:
        while True:
            # Recibir comandos sin bloquear (timeout corto)
            recv_task = asyncio.create_task(ws.receive_json())
            bus_task  = asyncio.create_task(sub.get())

            done, pending = await asyncio.wait(
                {recv_task, bus_task}, return_when=asyncio.FIRST_COMPLETED, timeout=send_interval
            )

            now = time.time()

            # Manejar lo recibido del cliente (p.ej. manual_cmd)
            if recv_task in done:
                try:
                    msg = recv_task.result()
                    topic = msg.get("topic")
                    data  = msg.get("data")
                    if topic and data is not None:
                        await BUS.publish(topic, data)
                except Exception:
                    pass

            # Capturar el último mensaje del bus (coalescing)
            if bus_task in done:
                try:
                    topic, data = bus_task.result()
                    last_msgs[topic] = data  # guardamos solo el más reciente por tópico
                except Exception:
                    pass

            # Throttle: solo enviar si pasó el intervalo
            if now - last_send >= send_interval and last_msgs:
                # backpressure: si el cliente está saturado, saltamos envío
                # (en navegador puedes revisar ws.bufferedAmount con JS; en server no)
                try:
                    # enviamos todos los últimos “coalesced” acumulados desde el último tick
                    for topic, data in list(last_msgs.items()):
                        await ws.send_json({"topic": topic, "data": data})
                    last_msgs.clear()
                    last_send = now
                except Exception:
                    # si falla (cliente desconectado), salimos
                    break

            # cancelar pendientes para evitar fugas
            for p in pending: 
                p.cancel()

    except WebSocketDisconnect:
        pass
    finally:
        sub.close()
