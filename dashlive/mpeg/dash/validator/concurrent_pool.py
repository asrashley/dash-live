#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import asyncio
import concurrent.futures
from typing import Callable

from .pool import AsyncPoolContextManager, WorkerPool
from .progress import Progress

class ConcurrentAsyncPoolContextManager(AsyncPoolContextManager):
    executor: concurrent.futures.Executor
    tasks: list[asyncio.Future]
    loop: asyncio.AbstractEventLoop

    def __init__(self, executor: concurrent.futures.Executor,
                 progress: Progress | None) -> None:
        super().__init__(progress)
        self.executor = executor
        self.loop = asyncio.get_running_loop()
        self.tasks = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        todo: int = len(self.tasks)
        await asyncio.gather(*self.tasks)
        if self.progress:
            self.progress.inc(todo)

    def submit(self, fn: Callable, *args) -> asyncio.Future:
        if self.progress:
            self.progress.add_todo(1)
        future: asyncio.Future = self.loop.run_in_executor(self.executor, fn, *args)
        self.tasks.append(future)
        return future


class ConcurrentWorkerPool(WorkerPool):
    executor: concurrent.futures.Executor
    tasks: set[asyncio.Future]

    def __init__(self, executor: concurrent.futures.Executor) -> None:
        self.executor = executor
        self.tasks = set()

    def group(self, progress: Progress | None = None) -> AsyncPoolContextManager:
        """
        Creates a new task group that will wait for their completion when
        the context manager exits.
        """
        return ConcurrentAsyncPoolContextManager(self.executor, progress)

    def submit(self, fn: Callable, *args) -> asyncio.Future:
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        future: asyncio.Future = loop.run_in_executor(self.executor, fn, *args)
        self.tasks.add(future)
        return future
