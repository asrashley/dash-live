#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import NamedTuple

class StreamFixture(NamedTuple):
    name: str
    title: str
    segment_duration: float  # in seconds
    media_duration: float  # in seconds


BBB_FIXTURE = StreamFixture(
    name="bbb",
    title="Big Buck Bunny",
    media_duration=40,
    segment_duration=4)

