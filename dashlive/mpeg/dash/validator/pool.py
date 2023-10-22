from abc import ABC, abstractmethod
import asyncio

class WorkerPool(ABC):

    @abstractmethod
    def submit(self, fn, *args, **kwargs) -> asyncio.Future:
        ...

    @abstractmethod
    def wait_for_completion(self, timeout: int) -> list[str]:
        ...
