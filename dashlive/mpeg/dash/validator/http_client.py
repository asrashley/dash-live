#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Protocol

class HttpClient(Protocol):
    def get(self, url: str, headers: dict | None = None,
            params=None,
            status: int | None = None,
            xhr: bool = False):
        ...
