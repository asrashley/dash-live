from abc import ABC, abstractmethod

from .media_create_options import MediaCreateOptions


class MediaCreationTask(ABC):
    options: MediaCreateOptions

    def __init__(self, options: MediaCreateOptions) -> None:
        self.options = options

    @abstractmethod
    def run(self) -> None:
        ...