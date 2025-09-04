#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from enum import IntEnum
from typing import NamedTuple

class VideoEncodingParameters(NamedTuple):
    width: int
    height: int
    bitrate: int
    codecString: str | None


class AudioEncodingParameters(NamedTuple):
    bitrate: int
    codecString: str
    channels: int


HD_BITRATE_LADDER: list[VideoEncodingParameters] = [
    VideoEncodingParameters(1280, 720, 4900, "avc1.640020"),
    VideoEncodingParameters(1280, 720, 3200, "avc1.64001F"),
    VideoEncodingParameters(1024, 576, 2300, "avc1.64001F"),
    VideoEncodingParameters(800, 450, 1650, "avc1.64001E"),
    VideoEncodingParameters(640, 360, 1150, "avc1.64001E"),
    VideoEncodingParameters(512, 288, 800, "avc1.640015"),
    VideoEncodingParameters(352, 198, 500, "avc1.640014"),
]

HD_HQ_BITRATE_LADDER: list[VideoEncodingParameters] = [
    VideoEncodingParameters(1920, 1080, 8600, "avc1.64002A"),
    *HD_BITRATE_LADDER,
]

SD_BITRATE_LADDER: list[VideoEncodingParameters] = [
    VideoEncodingParameters(896, 504, 1700, "avc1.64001E"),
    VideoEncodingParameters(640, 360, 1150, "avc1.64001E"),
    VideoEncodingParameters(512, 288, 800, "avc1.640015"),
    VideoEncodingParameters(352, 198, 500, "avc1.640014"),
]

MOBILE_BITRATE_LADDER: list[VideoEncodingParameters] = [
    VideoEncodingParameters(800, 450, 1650, "avc1.64001E"),
    VideoEncodingParameters(640, 360, 1150, "avc1.64001E"),
    VideoEncodingParameters(512, 288, 800, "avc1.640015"),
    VideoEncodingParameters(352, 198, 500, "avc1.640014"),
    VideoEncodingParameters(320, 180, 300, "avc1.640014"),
    VideoEncodingParameters(320, 180, 200, "avc1.4D4014"),
]


class BitrateProfiles(IntEnum):
    DEFAULT = 1
    MOBILE = 2
    SD = 3
    HD = 4
    HQ = 5

    @classmethod
    def keys(cls) -> list[str]:
        """get list of items in this enum"""
        return sorted(cls.__members__.keys())  # type: ignore

    @classmethod
    def from_string(cls, name: str) -> "BitrateProfiles":
        """
        Create a profile from a string
        """
        name = name.strip().upper()
        return cls[name]


BITRATE_PROFILES: dict[BitrateProfiles, list[VideoEncodingParameters]] = {
    BitrateProfiles.HQ: HD_HQ_BITRATE_LADDER,
    BitrateProfiles.HD: HD_BITRATE_LADDER,
    BitrateProfiles.SD: SD_BITRATE_LADDER,
    BitrateProfiles.MOBILE: MOBILE_BITRATE_LADDER,
    BitrateProfiles.DEFAULT: HD_HQ_BITRATE_LADDER,
}
