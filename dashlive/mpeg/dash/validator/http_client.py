#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from abc import abstractmethod
from typing import Protocol

from lxml import etree

from dashlive.utils.json_object import JsonObject

class HttpResponse(Protocol):
    status_code: int

    @property
    def xml(self) -> etree.Element:
        raise Exception("Not implemented")

    @property
    def json(self) -> JsonObject:
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
