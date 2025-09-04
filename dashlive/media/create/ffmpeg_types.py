#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from typing import TypedDict

class FfmpegStreamInfo(TypedDict):
    codec_type: str
    display_aspect_ratio: str
    avg_frame_rate: str
    width: int
    height: int


class FfmpegFormatInfo(TypedDict):
    duration: float


class FfmpegMediaInfo(TypedDict):
    streams: list[FfmpegStreamInfo]
    format: FfmpegFormatInfo
