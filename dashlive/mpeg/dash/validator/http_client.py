#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from abc import ABC, abstractmethod
from typing import Protocol

class HttpResponse(ABC):
    @property
    def xml(self):
        raise Exception("Not implemented")

    @property
    def forms(self, id):
        raise Exception("Not implemented")

    @property
    def json(self):
        raise Exception("Not implemented")

    @abstractmethod
    def get_data(self, as_text: bool) -> bytes | str:
        raise Exception("Not implemented")


class HttpClient(Protocol):
    async def head(self, url: str, headers: dict | None = None,
                   params=None,
                   status: int | None = None,
                   xhr: bool = False) -> HttpResponse:
        ...

    async def get(self, url: str, headers: dict | None = None,
                  params=None,
                  status: int | None = None,
                  xhr: bool = False) -> HttpResponse:
        ...
