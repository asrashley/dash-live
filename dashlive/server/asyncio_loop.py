#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import asyncio
from threading import Thread
from typing import Protocol

class AsyncLoopOwner(Protocol):
    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def run_coroutine(self, fn, *args, **kwargs) -> asyncio.Future:
        ...


class AsyncioLoop(AsyncLoopOwner):
    """
    This class provides a single background thread that runs the asyncio
    main loop. It allows running async functions in a application doesn't
    run asyncio main loop from its main() function.
    """

    thread: Thread | None
    loop: asyncio.AbstractEventLoop | None
    _started: bool

    def __init__(self) -> None:
        self._started = False
        self.loop = None
        self.thread = None

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self.loop = asyncio.new_event_loop()
        self.thread = Thread(target=self._start_background_loop, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        loop = self.loop
        thread = self.thread
        self.thread = None
        self.loop = None
        loop.stop()
        thread.join(0.5)

    def run_coroutine(self, fn, *args, **kwargs) -> asyncio.Future:
        if self.loop is None:
            raise RuntimeError('asyncio loop has been stopped')
        return asyncio.run_coroutine_threadsafe(fn(*args, **kwargs), self.loop)

    def _start_background_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_forever()
        finally:
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
