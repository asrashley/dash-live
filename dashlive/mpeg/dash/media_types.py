#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from enum import Enum

class MediaType(Enum):
    AUDIO = 'audio'
    VIDEO = 'video'
    APPLICATION = 'application'
    TEXT = 'text'

    @classmethod
    def all(cls) -> set["MediaType"]:
        return set(cls.__members__.values())

    @classmethod
    def from_string(cls, name: str) -> set["MediaType"]:
        if ',' in name:
            names: set[MediaType] = {
                cls[nm.strip().upper()] for nm in name.split(',')
            }
            return names
        name = name.strip().upper()
        if name == 'ANY':
            return cls.all()
        return set([cls[name]])
