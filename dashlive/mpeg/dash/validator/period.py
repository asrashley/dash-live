#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import asyncio
import datetime

from dashlive.mpeg.dash.representation import Representation as ServerRepresentation
from dashlive.utils.date_time import from_isodatetime

from .adaptation_set import AdaptationSet
from .dash_element import DashElement
from .events import EventStream
from .validation_flag import ValidationFlag

class Period(DashElement):
    id: str | int | None
    adaptation_sets: list[AdaptationSet]
    event_streams: list[EventStream]
    start: datetime.timedelta | None
    duration: datetime.timedelta | None

    attributes = [
        ('id', str, None),
        ('start', from_isodatetime, None),
        ('duration', from_isodatetime, DashElement.Parent),
    ]

    def __init__(self, period, parent) -> None:
        super().__init__(period, parent)
        self.adaptation_sets = []
        self.event_streams = []
        if self.start is None:
            self.start = datetime.timedelta()
            prev_period: Period | None = self.previous_peer()
            if prev_period and prev_period.duration:
                self.start = prev_period.start + prev_period.duration
        adps = period.findall('./dash:AdaptationSet', self.xmlNamespaces)
        self.adaptation_sets = [AdaptationSet(a, self) for a in adps]
        evs = period.findall('./dash:EventStream', self.xmlNamespaces)
        self.event_streams = [EventStream(r, self) for r in evs]
        next_id: int = 0
        for adp in self.adaptation_sets:
            if adp.id is not None:
                next_id = max(next_id, adp.id)
        next_id += 1
        self.target_duration: datetime.timedelta | None = None
        if self.options.duration:
            self.target_duration = datetime.timedelta(seconds=self.options.duration)
            if self.duration is not None:
                self.target_duration = min(self.target_duration, self.duration)
        for adp in self.adaptation_sets:
            if adp.id is None:
                adp.id = next_id
                next_id += 1

    async def prefetch_media_info(self) -> bool:
        self.progress.add_todo(len(self.adaptation_sets))
        futures = {
            adp.prefetch_media_info() for adp in self.adaptation_sets}
        results = await asyncio.gather(*futures)
        self.progress.inc()
        return False not in results

    async def merge_previous_element(self, prev: "Period") -> bool:
        self.log.debug('Merging previous Period element')
        adp_map = {}
        for idx, adp in enumerate(self.adaptation_sets):
            adp_map[adp.id] = adp
        futures = []
        for idx, adp in enumerate(prev.adaptation_sets):
            try:
                futures.append(adp_map[adp.id].merge_previous_element(adp))
            except KeyError as err:
                self.log.debug('New AdaptationSet %s', err)
        results = await asyncio.gather(*futures)
        return False not in results

    def get_codecs(self) -> set[str]:
        codecs = set()
        for adp in self.adaptation_sets:
            codecs.update(adp.get_codecs())
        return codecs

    def set_representation_info(self, info: ServerRepresentation):
        for a in self.adaptation_sets:
            a.set_representation_info(info)

    def children(self) -> list[DashElement]:
        return self.adaptation_sets + self.event_streams

    def finished(self) -> bool:
        for child in self.children():
            if not child.finished():
                self.log.debug('AdaptationSet %d in period %s not finished',
                               child.id, self.id)
                return False
        self.log.debug('period %s has finished', self.id)
        return True

    def get_duration(self) -> datetime.timedelta:
        if self.duration:
            return self.duration
        return self.parent.get_duration()

    def get_duration_as_timescale(self, timescale: int) -> int:
        dur = self.get_duration()
        if dur is None:
            return 0
        return int(dur.total_seconds() * timescale)

    def availability_start_time(self) -> datetime.datetime | None:
        ast = self.parent.availabilityStartTime
        if ast is None:
            return None
        return ast + self.start

    def num_tests(self) -> int:
        count = 0
        if ValidationFlag.PERIOD in self.options.verify:
            count += 1
        for adap_set in self.adaptation_sets:
            count += adap_set.num_tests()
        for evs in self.event_streams:
            count += evs.num_tests()
        return count

    async def validate(self) -> None:
        if ValidationFlag.PERIOD in self.options.verify:
            self.validate_self()
        futures = []
        for adap_set in self.adaptation_sets:
            futures.append(adap_set.validate())
        for evs in self.event_streams:
            futures.append(evs.validate())
        await asyncio.gather(*futures)

    def validate_self(self) -> None:
        if self.mode == 'live':
            self.attrs.check_not_none(
                self.id, msg='id is mandatory for a live stream', clause='5.3.2.2')
        self.progress.inc()
