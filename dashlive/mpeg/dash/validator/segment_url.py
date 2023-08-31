#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
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
