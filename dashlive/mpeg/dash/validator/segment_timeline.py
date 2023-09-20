#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from typing import NamedTuple

from .dash_element import DashElement

class SegmentEntry(NamedTuple):
    start: int | None
    duration: int

class SegmentTimeline(DashElement):
    def __init__(self, timeline: list[dict], parent: DashElement) -> None:
        super().__init__(timeline, parent)
        self.segments: list[SegmentEntry] = []
        start = None
        self.duration = 0
        for idx, seg in enumerate(timeline):
            t = seg.get('t')
            duration = int(seg.get('d'), 10)
            start = int(t, 10) if t is not None else start
            repeat = int(seg.get('r', '0')) + 1
            if not self.attrs.check_not_none(
                    start, msg='start attribute is missing for first entry in SegmentTimeline'):
                start = 0
            if repeat < 1:
                # r < 0 is a special case that means repeat until next S element or
                # end of Period
                if idx < (len(timeline) - 1):
                    next_seg = timeline[idx + 1]
                    next_t = next_seg.get('t')
                    if not self.attrs.check_not_none(
                            next_t, 'S@t is missing, following an S element with negative S@r'):
                        continue
                    repeat = int((int(next_t, 10) - start) // duration)
                else:
                    timescale = parent.get_timescale()
                    period = parent.find_parent('Period')
                    if not self.elt.check_not_none(period, msg='Failed to find Period element'):
                        continue
                    repeat = int(period.get_duration_as_timescale(timescale) // duration)
            for r in range(repeat):
                self.segments.append(SegmentEntry(start, duration))
                start += duration
                self.duration += duration

    def validate(self, depth: int = -1) -> None:
        pass

    def children(self) -> list[DashElement]:
        return []
