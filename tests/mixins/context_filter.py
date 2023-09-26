#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import logging
from typing import AbstractSet

class ContextFilter(logging.Filter):
    def __init__(self, fields: AbstractSet) -> None:
        self.data: dict[str, str] = {}
        for name in fields:
            self.data[name] = ''

    def reset(self) -> None:
        for key in self.data.keys():
            self.data[key] = ''

    def add_item(self, key: str, value: str) -> None:
        self.data[key] = value

    def __delitem__(self, name: str) -> None:
        if name in self.data:
            self.data[name] = ''

    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in self.data.items():
            object.__setattr__(record, key, value)
        return True
