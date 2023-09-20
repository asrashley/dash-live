#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from urllib.parse import urlparse

from .dash_element import DashElement
from .http_range import HttpRange

class SegmentURL(DashElement):
    attributes = [
        ('media', str, None),
        ('mediaRange', HttpRange, None),
        ('index', str, None),
        ('indexRange', HttpRange, None),
    ]

    def validate(self, depth: int = -1) -> None:
        self.checkIsNotNone(self.media)
        self.checkIsNotNone(self.index)
        url = urlparse(self.index)
        self.attrs.check_includes(
            {'http', 'https'}, url.scheme,
            template=r'Expected index URL HTTP scheme {0} but got {1}: ' + self.index)
        url = urlparse(self.media)
        self.attrs.check_includes(
            {'http', 'https'}, url.scheme,
            template=r'Expected media URL HTTP scheme {0} but got {1}: ' + self.media)

    def children(self) -> list[DashElement]:
        return []
