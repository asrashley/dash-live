from dataclasses import dataclass
from datetime import timedelta

@dataclass(slots=True, frozen=True)
class StreamTimingReference:
    media_name: str
    media_duration: int  # in timescale units
    num_media_segments: int
    segment_duration: int  # in timescale units
    timescale: int  # ticks per second

    def media_duration_timedelta(self) -> timedelta:
        seconds = self.media_duration / float(self.timescale)
        return timedelta(seconds=seconds)

    def toJSON(self, pure: bool = False) -> dict:
        return {
            'media_name': self.media_name,
            'media_duration': self.media_duration,
            'num_media_segments': self.num_media_segments,
            'segment_duration': self.segment_duration,
            'timescale': self.timescale
        }
