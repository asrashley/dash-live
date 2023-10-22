import asyncio
import traceback

import asyncio_gevent
import gevent
import gevent.pool

from .pool import WorkerPool

class GeventWorkerPool(WorkerPool):
    def __init__(self, maxsize: int) -> None:
        if maxsize < 1:
            self.pool = gevent.get_hub().threadpool
        else:
            self.pool = gevent.pool.Pool(maxsize, hub=gevent.get_hub())
        self.tasks = set()

    def submit(self, fn, *args, **kwargs) -> asyncio.Future:
        #greenlet = gevent.Greenlet.spawn(fn, *args, **kwargs)
        # greenlet = group.apply_async(fn, *args, **kwargs)
        greenlet = self.pool.apply_async(fn, *args, **kwargs)
        self.tasks.add(greenlet)
        future = asyncio_gevent.greenlet_to_future(greenlet)
        # greenlet.start()
        return future

    def wait_for_completion(self) -> list[str]:
        errors: list[Exception] = []
        
        with gevent.iwait(self.tasks) as it:
            for task in it:
                if task.successful():
                    continue
                print(task.exception)
                errors.append(f'{exc}')
        self.tasks = set()
        return errors
