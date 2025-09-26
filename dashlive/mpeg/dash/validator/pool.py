from abc import ABC, abstractmethod
import asyncio
from typing import Callable

from .progress import Progress

class AsyncPoolContextManager(ABC):
    progress: Progress | None

    def __init__(self, progress: Progress | None) -> None:
        self.progress = progress

    @abstractmethod
    async def __aenter__(self) -> "AsyncPoolContextManager":
        ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc, tb) -> None:
        ...

    @abstractmethod
    def submit(self, fn: Callable, *args) -> asyncio.Future:
        ...


class WorkerPool(ABC):

    @abstractmethod
    def submit(self, fn: Callable, *args, **kwargs) -> asyncio.Future:
        ...

    @abstractmethod
    def group(self, progress: Progress | None = None) -> AsyncPoolContextManager:
        ...
