import asyncio

import asyncio_gevent
import gevent
import gevent.pool
from gevent.threadpool import ThreadPoolExecutor

from .pool import WorkerPool

class AsyncPoolContextManager:
    next_id = 1

    def __init__(self, executor: ThreadPoolExecutor) -> None:
        self.executor = executor
        self.tasks = []
        self.tid = self.__class__.next_id
        self.__class__.next_id += 1

    async def __aenter__(self):
        print(f'enter TaskGroup id={self.tid}')
        return self

    async def __aexit__(self, exc_type, exc, tb):
        print(f'TaskGroup await id={self.tid} len=', len(self.tasks))
        print(await asyncio.gather(*self.tasks, return_exceptions=True))

    def submit(self, async_fn, *args, **kwargs) -> asyncio.Future:
        print(f'TaskGroup submit id={self.tid}')
        try:
            sync_fn = asyncio_gevent.async_to_sync(async_fn)
            future = self.executor.submit(sync_fn, *args, **kwargs)
            print(f'submit task id={self.tid} future=', type(future))
            self.tasks.append(future)
            print(f'TaskGroup submit id={self.tid} success', len(self.tasks))
        except Exception as err:
            print('Submit exception', type(err), err)
            raise
        return future


class GeventWorkerPool(WorkerPool):
    def __init__(self, executor: ThreadPoolExecutor) -> None:
        self.executor = executor

    def group(self) -> AsyncPoolContextManager:
        """
        Creates a new task group that will wait for their completion when
        the context manager exits.
        """
        return AsyncPoolContextManager(self.executor)

    def submit(self, fn, *args, **kwargs) -> asyncio.Future:
        print('submit task', fn)
        future = self.executor.submit(fn, *args, **kwargs)
        print('submit task future=', type(future))
        return future

    def wait_for_completion(self) -> list[str]:
        errors: list[Exception] = []

        with gevent.iwait(self.tasks) as it:
            for task in it:
                if task.successful():
                    continue
                errors.append(f'{task.exception}')
        self.tasks = set()
        return errors
