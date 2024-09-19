#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from typing import Any, ClassVar
from urllib.parse import urlparse

from .dash_element import DashElement
from .http_range import HttpRange

class SegmentURL(DashElement):
    attributes: ClassVar[list[tuple[str, Any, Any]]] = [
        ('media', str, None),
        ('mediaRange', HttpRange, None),
        ('index', str, None),
        ('indexRange', HttpRange, None),
    ]

    def __repr__(self) -> str:
        params: list[str] = []
        if self.media:
            params.append(f'media={self.media}')
        if self.mediaRange:
            params.append(f'mediaRange={self.mediaRange}')
        if self.index:
            params.append(f'index={self.index}')
        if self.indexRange:
            params.append(f'indexRange={self.indexRange}')
        txt = ', '.join(params)
        return f'SegmentURL({txt})'

    async def validate(self) -> None:
        if self.attrs.check_not_none(self.index):
            url = urlparse(self.index)
            self.attrs.check_includes(
                {'http', 'https'}, url.scheme,
                msg=f'Expected HTTP(S) URL scheme for index but got "{self.index}"')
        if self.attrs.check_not_none(self.media):
            url = urlparse(self.media)
            self.attrs.check_includes(
                {'http', 'https'}, url.scheme,
                msg=r'Expected HTTP(S) URL scheme for media but got "{self.media}"')

    def children(self) -> list[DashElement]:
        return []
