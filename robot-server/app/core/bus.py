# app/core/bus.py
import asyncio
from collections import defaultdict
from typing import Any, Dict, Iterable, Tuple

class Subscriber:
    def __init__(self, queues: Iterable[asyncio.Queue]):
        self._queues = list(queues)

    async def get(self) -> Tuple[str, Any]:
        tasks = [asyncio.create_task(q.get()) for q in self._queues]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for p in pending:
            p.cancel()
        topic, data = list(done)[0].result()
        return topic, data

    def close(self):
        for q in self._queues:
            try:
                q.put_nowait(("__CLOSE__", None))
            except Exception:
                pass

class Bus:
    def __init__(self, maxsize:int=100):
        self._topics = defaultdict(lambda: asyncio.Queue(maxsize=maxsize))
        self._last = {}
    async def publish(self, topic, data):
        self._last[topic] = data
        q = self._topics[topic]
        # si la cola está llena, descarta el más antiguo (coalescing tipo drop-oldest)
        if q.full():
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
        await q.put((topic, data))

# Utilidad: “topic cache” seguro con defecto
async def last_or(bus: Bus, topic: str, default: Any):
    v = await bus.last(topic)
    return v if v is not None else default
