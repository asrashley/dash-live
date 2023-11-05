#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from .content_protection import ContentProtection
from .dash_element import DashElement
from .events import InbandEventStream
from .frame_rate_type import FrameRateType
from .segment_list_type import SegmentListType
from .segment_template import SegmentTemplate

class RepresentationBaseType(DashElement):
    attributes = [
        ('audioSamplingRate', int, None),
        ('codecs', str, None),
        ('profiles', str, None),
        ('width', int, None),
        ('height', int, None),
        ('frameRate', FrameRateType, None),
        ('mimeType', str, None),
    ]

    def __init__(self, elt, parent):
        super().__init__(elt, parent)
        prot = elt.findall('./dash:ContentProtection', self.xmlNamespaces)
        self.contentProtection = [ContentProtection(cp, self) for cp in prot]
        self.segmentTemplate = None
        templates = elt.findall('./dash:SegmentTemplate', self.xmlNamespaces)
        if len(templates):
            self.segmentTemplate = SegmentTemplate(templates[0], self)
        self.segmentList = None
        seg_list = elt.findall('./dash:SegmentList', self.xmlNamespaces)
        self.segmentList = [SegmentListType(s, self) for s in seg_list]
        ibevs = elt.findall('./dash:InbandEventStream', self.xmlNamespaces)
        self.event_streams = [InbandEventStream(r, self) for r in ibevs]

    def get_timescale(self) -> int:
        if self.segmentTemplate:
            return self.segmentTemplate.timescale
        if isinstance(self.parent, RepresentationBaseType):
            return self.parent.get_timescale()
        return 1

    def validate(self, depth: int = -1) -> None:
        if depth == 0:
            return
        for ev in self.event_streams:
            ev.validate(depth - 1)

    def children(self) -> list[DashElement]:
        return self.event_streams
