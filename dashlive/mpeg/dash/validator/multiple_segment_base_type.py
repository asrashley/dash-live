#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from .dash_element import DashElement, ParentAttribute
from .segment_base_type import SegmentBaseType
from .segment_timeline import SegmentTimeline

class MultipleSegmentBaseType(SegmentBaseType):
    attributes = SegmentBaseType.attributes + [
        ('duration', int, None),
        ('startNumber', int, ParentAttribute),
    ]

    def __init__(self, elt, parent):
        super().__init__(elt, parent)
        self.segmentTimeline = None
        timeline = elt.findall('./dash:SegmentTimeline', self.xmlNamespaces)
        if len(timeline):
            self.segmentTimeline = SegmentTimeline(timeline[0], self)
        self.BitstreamSwitching = None
        bss = elt.findall('./dash:BitstreamSwitching', self.xmlNamespaces)
        if len(bss):
            self.BitstreamSwitching = bss[0].text

    async def validate(self) -> None:
        await super().validate()
        if self.segmentTimeline is not None:
            # 5.3.9.2.1: The attribute @duration and the element SegmentTimeline
            # shall not be present at the same time.
            self.checkIsNone(self.duration)

    def children(self) -> list[DashElement]:
        rv = super().children()
        if self.segmentTimeline:
            rv.append(self.segmentTimeline)
        return rv
