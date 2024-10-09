#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from enum import IntEnum
from typing import ClassVar

from .media_types import MediaType

class ContentRole(IntEnum):
    """
    Enumerates all possible content roles
    """

    MAIN = 1
    ALTERNATE = 2
    SUPPLEMENTARY = 3
    CAPTION = 4
    SUBTITLE = 5
    COMMENTARY = 6
    DUB = 7
    DESCRIPTION = 8
    SIGN = 9
    METADATA = 10
    ENHANCED_AUDIO_INTELLIGIBILITY = 11
    EMERGENCY = 12
    FORCED_SUBTITLE = 13
    EASYREADER = 14
    KARAOKE = 15

    __USAGE: ClassVar[dict["ContentRole", str]] = {
        MAIN: 'any',
        ALTERNATE: 'any',
        SUPPLEMENTARY: 'any',
        CAPTION: 'video, text',
        SUBTITLE: 'video, text',
        COMMENTARY: 'audio, text',
        DUB: 'audio, text',
        DESCRIPTION: 'audio, text',
        SIGN: 'video',
        METADATA: 'text, application',
        ENHANCED_AUDIO_INTELLIGIBILITY: 'audio',
        EMERGENCY: 'any',
        FORCED_SUBTITLE: 'text',
        EASYREADER: 'text, video',
        KARAOKE: 'any'
    }

    @classmethod
    def all(cls) -> list["ContentRole"]:
        return [cls[key] for key in cls.__members__.keys()]

    @classmethod
    def from_string(cls, name: str) -> "ContentRole":
        """
        Create a ContentRole from a string
        """
        name = name.strip().upper()
        return cls[name]

    def usage(self) -> set[MediaType]:
        """
        Returns allowed media types for this role
        """
        use = ContentRole.__USAGE[self]
        return MediaType.from_string(use)
