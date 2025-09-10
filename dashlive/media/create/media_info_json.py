#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import NotRequired, TypedDict

class KeyInfoJson(TypedDict):
    kid: str
    key: NotRequired[str]
    computed: bool


class StreamInfoJson(TypedDict):
    directory: str
    title: str
    files: list[str]


class MediaInfoJson(TypedDict):
    keys: list[KeyInfoJson]
    streams: list[StreamInfoJson]
