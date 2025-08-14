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
    def __init__(self):
        self._topics: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._last: Dict[str, Any] = {}

    async def publish(self, topic: str, data: Any):
        self._last[topic] = data
        await self._topics[topic].put((topic, data))

    def subscribe(self, topics: Iterable[str]) -> Subscriber:
        queues = [self._topics[t] for t in topics]
        return Subscriber(queues)

    async def last(self, topic: str) -> Any:
        return self._last.get(topic)

# Utilidad: “topic cache” seguro con defecto
async def last_or(bus: Bus, topic: str, default: Any):
    v = await bus.last(topic)
    return v if v is not None else default
