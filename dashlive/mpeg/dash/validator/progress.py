#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from abc import ABC, abstractmethod

class Progress(ABC):
    def __init__(self):
        self.num_items: int = 1
        self.count: int = 0
        self.txt: str = ''

    def reset(self, num_items: int) -> None:
        self.num_items = num_items
        self.count = 0
        self._send_output()

    def inc(self) -> None:
        self.count += 1
        self._send_output()

    def text(self, text: str) -> None:
        self.txt = text
        self._send_output()

    def _send_output(self) -> None:
        pct = 100.0 * self.count / self.num_items
        self.send_progress(pct=pct, text=self.txt)

    @abstractmethod
    def send_progress(self, pct: float, text: str) -> None:
        ...

    @abstractmethod
    def aborted(self) -> bool:
        ...
