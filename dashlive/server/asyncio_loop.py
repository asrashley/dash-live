#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import asyncio
from threading import Thread

class AsyncioLoop:
    """
    This class provides a single background thread that runs the asyncio
    main loop. It allows running async functions in a application doesn't
    run asyncio main loop from its main() function.
    """

    def __init__(self) -> None:
        self._started = False
        self.loop = asyncio.new_event_loop()
        self.thread = Thread(target=self._start_background_loop, daemon=True)

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self.thread.start()

    def run_coroutine(self, fn, *args, **kwargs):
        return asyncio.run_coroutine_threadsafe(fn(*args, **kwargs), self.loop)

    def _start_background_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()


asyncio_loop = AsyncioLoop()
