#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .multiple_segment_base_type import MultipleSegmentBaseType
from .segment_url import SegmentURL

class SegmentListType(MultipleSegmentBaseType):
    def __init__(self, elt, parent):
        super().__init__(elt, parent)
        urls = elt.findall('./dash:SegmentURL', self.xmlNamespaces)
        self.segmentURLs = [SegmentURL(u, self) for u in urls]

    def validate(self, depth: int = -1) -> None:
        super().validate(depth)
        self.checkGreaterThan(len(self.segmentURLs), 0)
        self.checkGreaterThan(len(self.segmentURLs[0].initializationList), 0)
