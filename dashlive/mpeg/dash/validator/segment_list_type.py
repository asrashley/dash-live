#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import asyncio

from .dash_element import DashElement
from .multiple_segment_base_type import MultipleSegmentBaseType
from .segment_url import SegmentURL

class SegmentListType(MultipleSegmentBaseType):
    segmentURLs: list[SegmentURL]

    def __init__(self, elt, parent):
        super().__init__(elt, parent)
        urls = elt.findall('./dash:SegmentURL', self.xmlNamespaces)
        self.segmentURLs = [SegmentURL(u, self) for u in urls]

    async def validate(self) -> None:
        self.elt.check_greater_than(
            len(self.segmentURLs), 0,
            msg='Expected at least one media SegmentURL element')
        self.elt.check_greater_than(
            len(self.initializationList), 0,
            msg='Expected at least one Initialization element')
        futures = {url.validate() for url in self.segmentURLs}
        futures.add(super().validate())
        await asyncio.gather(*futures)

    def children(self) -> list[DashElement]:
        return super().children() + self.segmentURLs

    def __repr__(self) -> str:
        params: list[str] = []
        for item in self.children():
            params.append(str(item))
        txt = ', '.join(params)
        return f'SegmentListType({txt})'
