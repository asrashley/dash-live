#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from abc import ABC, abstractmethod
import sys

class Progress(ABC):
    def __init__(self):
        self.num_items: int = 1
        self.count: int = 0
        self.txt: str = ''

    def reset(self, num_items: int) -> None:
        self.num_items = num_items
        self.count = 0
        self._send_output()

    def add_todo(self, num: int) -> None:
        self.num_items += num

    def inc(self, count: int = 1) -> None:
        self.count += count
        self._send_output()

    def finished(self, text: str) -> None:
        self.count = self.num_items
        self.txt = text
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


class NullProgress(Progress):
    def send_progress(self, pct: float, text: str) -> None:
        pass

    def aborted(self) -> bool:
        return False

class ConsoleProgress(Progress):
    def __init__(self):
        super().__init__()
        self._aborted = False

    def send_progress(self, pct: float, text: str) -> None:
        sys.stdout.write(f'\r{pct:#05.1f}: {text}     ')
        sys.stdout.flush()

    def aborted(self) -> bool:
        return self._aborted

    def abort(self) -> None:
        self._aborted = True
