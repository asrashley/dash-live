#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from dataclasses import dataclass
from typing import NamedTuple

from dashlive.mpeg.dash.content_role import ContentRole

@dataclass
class StreamFixture:
    """
    Describes one test stream
    """
    name: str
    title: str
    segment_duration: float  # in seconds
    media_duration: float  # in seconds

class FixtureTrack(NamedTuple):
    """
    Describes one track in a test multi-period stream
    """
    ttype: str  # "video", "audio", etc
    tid: int
    role: ContentRole

class FixturePeriod(NamedTuple):
    """
    Describes one Period in a test multi-period stream
    """
    pid: str
    fixture: StreamFixture
    start: int
    end: int
    tracks: list[FixtureTrack]

class MultiPeriodStreamFixture(StreamFixture):
    periods: list[FixturePeriod]

    def __init__(self, periods: list[FixturePeriod], **kwargs) -> None:
        super().__init__(**kwargs)
        self.periods = periods


BBB_FIXTURE = StreamFixture(
    name="bbb",
    title="Big Buck Bunny",
    media_duration=40,
    segment_duration=4)

TEARS_FIXTURE = StreamFixture(
    name="tears",
    title="Tears of Steel",
    media_duration=64,
    segment_duration=4)


MPS_FIXTURE = MultiPeriodStreamFixture(
    name="testmps",
    title="Example multi-period stream",
    segment_duration=0,
    media_duration=(
        BBB_FIXTURE.media_duration - 2 * BBB_FIXTURE.segment_duration +
        TEARS_FIXTURE.media_duration - 5 * TEARS_FIXTURE.segment_duration),
    periods=[
        FixturePeriod(pid="p1", fixture=BBB_FIXTURE, start=1, end=1,
                      tracks=[
                          FixtureTrack('video', 1, ContentRole.MAIN),
                          FixtureTrack('audio', 2, ContentRole.MAIN),
                      ]),
        FixturePeriod(pid="p2", fixture=TEARS_FIXTURE, start=2, end=3,
                      tracks=[
                          FixtureTrack('video', 1, ContentRole.MAIN),
                          FixtureTrack('audio', 2, ContentRole.MAIN),
                      ]),
    ])
