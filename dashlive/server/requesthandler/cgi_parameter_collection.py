#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import NamedTuple

class CgiParameterCollection(NamedTuple):
    audio: dict[str, str]
    video: dict[str, str]
    text: dict[str, str]
    manifest: dict[str, str]
    patch: dict[str, str]
    time: dict[str, str]
