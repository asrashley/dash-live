#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import asyncio
from collections.abc import Iterable
import datetime

from dashlive.mpeg.dash.representation import Representation as ServerRepresentation
from dashlive.utils.date_time import from_isodatetime

from .adaptation_set import AdaptationSet
from .dash_element import DashElement, ValidateTask
from .events import EventStream
from .roundrobin import roundrobin
from .validation_flag import ValidationFlag

class Period(DashElement):
    attributes = [
        ('id', str, None),
        ('start', from_isodatetime, None),
        ('duration', from_isodatetime, DashElement.Parent),
    ]

    def __init__(self, period, parent):
        super().__init__(period, parent)
        if self.parent.mpd_type == 'dynamic':
            if self.start is None:
                self.start = parent.availabilityStartTime
            else:
                self.start = parent.availabilityStartTime + \
                    datetime.timedelta(seconds=self.start.total_seconds())
        adps = period.findall('./dash:AdaptationSet', self.xmlNamespaces)
        self.adaptation_sets = [AdaptationSet(a, self) for a in adps]
        evs = period.findall('./dash:EventStream', self.xmlNamespaces)
        self.event_streams = [EventStream(r, self) for r in evs]
        next_id = 0
        for adp in self.adaptation_sets:
            if adp.id is not None:
                next_id = max(next_id, adp.id)
        next_id += 1
        for adp in self.adaptation_sets:
            if adp.id is None:
                adp.id = next_id
                next_id += 1

    async def prefetch_media_info(self) -> None:
        self.progress.add_todo(len(self.adaptation_sets))
        futures = [
            adp.prefetch_media_info() for adp in self.adaptation_sets]
        await asyncio.gather(*futures)
        self.progress.inc()

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

    def set_representation_info(self, info: ServerRepresentation):
        for a in self.adaptation_sets:
            a.set_representation_info(info)

    def children(self) -> list[DashElement]:
        return self.adaptation_sets + self.event_streams

    def finished(self) -> bool:
        for child in self.children():
            if not child.finished():
                self.log.debug('Period %s not finished', self.id)
                return False
        self.log.debug('Period %s finished', self.id)
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

    def num_tests(self) -> int:
        count = 0
        if ValidationFlag.PERIOD in self.options.verify:
            count += 1
        for adap_set in self.adaptation_sets:
            count += adap_set.num_tests()
        for evs in self.event_streams:
            count += evs.num_tests()
        return count

    def validate(self) -> None:
        for fn in self.validation_tasks():
            fn()
            if self.progress.aborted():
                return
        if self.pool is not None:
            for err in self.pool.wait_for_completion():
                self.elt.add_error(f'Exception: {err}')

    async def validate(self) -> None:
        if ValidationFlag.PERIOD in self.options.verify:
            await self.validate_self()
        futures = []
        for adap_set in self.adaptation_sets:
            futures.append(adap_set.validate())
        for evs in self.event_streams:
            futures.append(evs.validate())
        await asyncio.gather(*futures)
        
    async def validate_self(self) -> None:
        return
