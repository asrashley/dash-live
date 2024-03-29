#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import asyncio
import concurrent.futures

from .pool import WorkerPool
from .progress import Progress

class AsyncPoolContextManager:
    def __init__(self, executor: concurrent.futures.Executor,
                 progress: Progress | None) -> None:
        self.executor = executor
        self.loop = asyncio.get_running_loop()
        self.tasks = []
        self.progress = progress

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        todo = len(self.tasks)
        await asyncio.gather(*self.tasks)
        if self.progress:
            self.progress.inc(todo)

    def submit(self, fn, *args) -> asyncio.Future:
        if self.progress:
            self.progress.add_todo(1)
        future = self.loop.run_in_executor(self.executor, fn, *args)
        self.tasks.append(future)
        return future


class ConcurrentWorkerPool(WorkerPool):
    def __init__(self, executor: concurrent.futures.Executor) -> None:
        self.executor = executor
        self.tasks = set()

    def group(self, progress: Progress | None = None) -> AsyncPoolContextManager:
        """
        Creates a new task group that will wait for their completion when
        the context manager exits.
        """
        return AsyncPoolContextManager(self.executor, progress)

    def submit(self, fn, *args) -> asyncio.Future:
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(self.executor, fn, *args)
        self.tasks.add(future)
        return future

    async def wait_for_completion(self) -> list[str]:
        errors: list[Exception] = []
        for result in await asyncio.gather(*list(self.tasks), return_exceptions=True):
            if result is not None:
                errors.append(result)
        self.tasks = set()
        return errors
