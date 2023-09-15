#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import datetime

from dashlive.utils.date_time import from_isodatetime

from .adaptation_set import AdaptationSet
from .dash_element import DashElement
from .events import EventStream

class Period(DashElement):
    attributes = [
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
        for evs in self.event_streams:
            if self.progress.aborted():
                return
            evs.validate(depth - 1)
            self.progress.inc()
