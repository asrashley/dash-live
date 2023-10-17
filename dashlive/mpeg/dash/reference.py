from dataclasses import dataclass
from datetime import timedelta
from typing import AbstractSet

from dashlive.utils.json_object import JsonObject
from dashlive.utils.date_time import timecode_to_timedelta

@dataclass(slots=True, frozen=True)
class StreamTimingReference:
    media_name: str
    media_duration: int  # in timescale units
    num_media_segments: int
    segment_duration: int  # in timescale units
    timescale: int  # ticks per second

    def media_duration_timedelta(self) -> timedelta:
        return timecode_to_timedelta(self.media_duration, self.timescale)

    def media_duration_using_timescale(self, timescale: int) -> int:
        """
        duration of the reference media, in units of the specified timescale
        """
        return self.media_duration * timescale // self.timescale

    def toJSON(self, pure: bool = False, exclude: AbstractSet | None = None) -> JsonObject:
        rv: JsonObject = {
            'media_name': self.media_name,
            'media_duration': self.media_duration,
            'num_media_segments': self.num_media_segments,
            'segment_duration': self.segment_duration,
            'timescale': self.timescale
        }
        if exclude is None:
            return rv
        for k in rv.keys():
            if k in exclude:
                del rv[k]
        return rv
