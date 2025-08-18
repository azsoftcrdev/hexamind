# app/motion/controller_vel.py
import asyncio, time, threading
from dataclasses import dataclass
from typing import Optional
from MutoLib import Muto

@dataclass
class VelSP:
    x:int=0; y:int=0; z:int=0           
    speed:int=2                     
    ts:float=time.time()
    gen:int=0

class MotionControllerVel:
    def __init__(self, hz:float=15.0, deadman_s:float=0.8):
        self.bot = Muto() 
        self.sp = VelSP()
        self._lock = threading.Lock()
        self._hz = hz
        self._deadman = deadman_s
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def start(self, loop: asyncio.AbstractEventLoop):
        if self._task and not self._task.done(): return
        self._running = True
        self._task = loop.create_task(self._loop())

    def stop_loop(self): self._running = False

    # ------- API pública (latest-wins) -------
    def set_vel(self, x:int, y:int, z:int, speed:Optional[int]=None):
        x = max(-30, min(30, int(x)))
        y = max(-30, min(30, int(y)))
        z = max(-30, min(30, int(z)))
        with self._lock:
            self.sp.x, self.sp.y, self.sp.z = x, y, z
            if speed is not None: self.sp.speed = max(1, min(5, int(speed)))
            self.sp.ts = time.time(); self.sp.gen += 1
        return self.snapshot()

    def stop(self):
        return self.set_vel(0,0,0)

    def snapshot(self):
        with self._lock:
            return dict(x=self.sp.x,y=self.sp.y,z=self.sp.z,
                        speed=self.sp.speed, ts=self.sp.ts, gen=self.sp.gen)

    # ------- Bucle único que aplica el setpoint -------
    async def _loop(self):
        period = max(1.0/self._hz, 0.02)
        while self._running:
            await asyncio.sleep(period)
            with self._lock:
                sp = VelSP(**self.sp.__dict__)
            now = time.time()

            # Dead-man: si no hay “vida”, detén
            if (now - sp.ts) > self._deadman:
                try: self.bot.stay_put()
                except: pass
                continue

            try:
                self.bot.speed(sp.speed)      # nivel 1..5 (la lib lo invierte internamente)
                self.bot.move(sp.x, sp.y, sp.z)  # llamada CONTINUA (requerido por MutoLib)
            except Exception:

                pass
