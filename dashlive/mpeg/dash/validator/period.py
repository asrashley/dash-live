#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import datetime

from dashlive.mpeg.dash.representation import Representation as ServerRepresentation
from dashlive.utils.date_time import from_isodatetime

from .adaptation_set import AdaptationSet
from .dash_element import DashElement
from .events import EventStream

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

    def prefetch_media_info(self) -> None:
        self.progress.add_todo(len(self.adaptation_sets))
        for adp in self.adaptation_sets:
            adp.prefetch_media_info()
        if self.pool is not None:
            for err in self.pool.wait_for_completion():
                self.elt.add_error(f'Exception: {err}')
        self.progress.inc()

    def merge_previous_element(self, prev: "Period") -> bool:
        def make_adp_id(idx, adp):
            if adp.id is not None:
                return adp.id
            if adp.contentType or adp.lang:
                return f'{adp.contentType}:{adp.lang}'
            return f'{idx}'

        self.log.debug('Merging previous Period element')
        adp_map = {}
        for idx, adp in enumerate(self.adaptation_sets):
            aid = make_adp_id(idx, adp)
            adp_map[aid] = adp
        rv = True
        for idx, adp in enumerate(prev.adaptation_sets):
            aid = make_adp_id(idx, adp)
            try:
                if not adp_map[aid].merge_previous_element(adp):
                    rv = False
            except KeyError as err:
                self.log.debug('New AdaptationSet %s', err)
        return rv

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

    def num_tests(self, depth: int = -1) -> int:
        if depth == 0:
            return 0
        count = len(self.adaptation_sets) + len(self.event_streams)
        for adap_set in self.adaptation_sets:
            count += adap_set.num_tests(depth - 1)
        for evs in self.event_streams:
            count += evs.num_tests(depth - 1)
        return count

    def validate(self, depth: int = -1) -> None:
        if depth == 0:
            return
        for adap_set in self.adaptation_sets:
            if self.progress.aborted():
                return
            adap_set.validate(depth - 1)
            self.progress.inc()
        if self.pool is not None:
            for err in self.pool.wait_for_completion():
                self.elt.add_error(f'Exception: {err}')
        for evs in self.event_streams:
            if self.progress.aborted():
                return
            evs.validate(depth - 1)
            self.progress.inc()
