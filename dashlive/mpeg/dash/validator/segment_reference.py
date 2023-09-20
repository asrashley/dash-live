#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from .dash_element import DashElement
from .http_range import HttpRange

class SegmentReference(DashElement):
    REPR_FMT = r'SegmentReference(url={sourceURL}, duration={duration}, decode_time={decode_time}, mediaRange={mediaRange}'

    def __init__(self, parent, url, start, end, decode_time, duration):
        super().__init__(elt=None, url=url, parent=parent)
        self.sourceURL = url
        self.media = url
        self.mediaRange = HttpRange(start, end)
        self.decode_time = decode_time
        self.duration = duration

    def validate(self, depth: int = -1) -> None:
        self.elt.check_greater_than(self.duration, 0)

    def __repr__(self):
        return self.REPR_FMT.format(**self.__dict__)
