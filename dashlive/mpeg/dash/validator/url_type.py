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

class URLType(DashElement):
    attributes = [
        ("sourceURL", str, None),
        ("range", HttpRange, None),
    ]

    def validate(self, depth: int = -1) -> None:
        if not self.attrs.check_not_none(self.sourceURL, msg='souceURL is missing'):
            return
        url = urlparse(self.souceURL)
        self.attrs.check_includes(
            {'http', 'https'}, url.scheme,
            template=r'Expected HTTP scheme {0} but got {1}')

    def children(self) -> list[DashElement]:
        return []
