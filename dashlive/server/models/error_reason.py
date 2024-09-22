#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from enum import IntEnum
from typing import ClassVar

class ErrorReason(IntEnum):
    """
    Enumerates all reported media file errors
    """

    FILE_NOT_FOUND = 1
    NO_FRAGMENTS = 2
    INVALID_LANGUAGE_TAG = 3
    DUPLICATE_TRACK_IDS = 4
    FAILED_TO_DETECT_BITRATE = 5
    NOT_ENOUGH_FRAGMENTS = 6

    __descriptions: ClassVar[list[str]] = [
        '',
        'File not found',
        'Not an MP4 fragmented file',
        'The language tag must be a valid BCP-47 language tag, "und" or "zxx"',
        'Multiple files share the same track ID that use different codecs',
        (
            'Failed to detect the duration of file, which is needed to be able to ' +
            'calculate its bitrate'
        ),
        'File must contain at least two media fragments',
    ]

    @property
    def description(self) -> str:
        return ErrorReason.__descriptions[self.value]
