#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from enum import Flag, auto
from functools import reduce

class ValidationFlag(Flag):
    MANIFEST = auto()
    PERIOD = auto()
    ADAPTATION_SET = auto()
    REPRESENTATION = auto()
    MEDIA = auto()
    EVENTS = auto()
    CONTENT_PROTECTION = auto()

    @classmethod
    def all(cls) -> "ValidationFlag":
        return reduce(ValidationFlag.__or__, cls.__members__.values(),
                      ValidationFlag(0))
