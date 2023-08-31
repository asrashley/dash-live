#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from .dash_element import DashElement
from .http_range import HttpRange

class URLType(DashElement):
    attributes = [
        ("sourceURL", str, None),
        ("range", HttpRange, None),
    ]

    def validate(self, depth: int = -1) -> None:
        # TODO: check that the URL is valid
        pass
