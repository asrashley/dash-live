#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import collections

from .dash_element import DashElement

class SegmentTimeline(DashElement):
    SegmentEntry = collections.namedtuple(
        'SegmentEntry', ['start', 'duration'])

    def __init__(self, timeline, parent):
        super().__init__(timeline, parent)
        self.segments = []
        start = None
        self.duration = 0
        for seg in timeline:
            repeat = int(seg.get('r', '0')) + 1
            t = seg.get('t')
            start = int(t, 10) if t is not None else start
            if start is None and not self.options.strict:
                self.log.warning('start attribute is missing for first entry in SegmentTimeline')
                start = 0
            self.checkIsNotNone(start)
            duration = int(seg.get('d'), 10)
            for r in range(repeat):
                self.segments.append(self.SegmentEntry(start, duration))
                start += duration
                self.duration += duration

    def validate(self, depth: int = -1) -> None:
        pass
