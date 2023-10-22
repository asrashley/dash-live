import concurrent.futures
import traceback

from .pool import WorkerPool

class ConcurrentWorkerPool(WorkerPool):
    def __init__(self, executor: concurrent.futures.Executor) -> None:
        self.executor = executor
        self.tasks: set[concurrent.futures.Future] = set()

    def submit(self, fn, *args, **kwargs) -> concurrent.futures.Future:
        future = self.executor.submit(fn, *args, **kwargs)
        self.tasks.add(future)
        return future

    def wait_for_completion(self) -> list[str]:
        errors: list[Exception] = []
        for future in concurrent.futures.as_completed(self.tasks):
            try:
                future.result()
            except Exception as exc:
                print(exc)
                traceback.print_exc()
                errors.append(f'{exc}')
        self.tasks = set()
        return errors
