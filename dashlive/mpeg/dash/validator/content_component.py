#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from typing import Any, ClassVar

from langcodes import tag_is_valid
from lxml import etree as ET

from .dash_element import DashElement

class ContentComponent(DashElement):
    CONTENT_TYPES: ClassVar[set[str]] = {
        'application',
        'audio',
        'font',
        'image',
        'text',
        'video',
    }
    attributes: ClassVar[list[tuple[str, Any, Any]]] = [
        ('id', str, None),
        ('lang', str, None),
        ('contentType', str, None),
        ('par', str, None),
        ('tag', str, None),
    ]

    id: str | None
    lang: str | None
    contentType: str | None
    par: str | None
    tag: str | None

    def __init__(self,
                 xml: ET.ElementBase,
                 parent: DashElement | None) -> None:
        super().__init__(xml, parent)
        self.url = xml.text
        self.patch = None

    def children(self) -> list[DashElement]:
        return []

    async def validate(self) -> None:
        if self.lang not in {None, 'und', 'zxx'}:
            self.attrs.check_true(
                tag_is_valid(self.lang),
                msg=f'@id must be a valid BCP-47 tag, found "{self.lang}"',
                clause='5.3.4.2')
        if self.contentType is not None:
            self.attrs.check_includes(
                ContentComponent.CONTENT_TYPES,
                self.contentType,
                msg=f'Unexpected @contentType "{self.contentType}"',
                clause='5.3.4.2')
            if self.parent.contentType is not None:
                self.attrs.check_equal(
                    self.contentType, self.parent.contentType,
                    msg=(f'@contentType "{self.contentType}" doesn\'t match ' +
                         f'AdaptationSet@contentType "{self.parent.contentType}"'))
        if self.par is not None:
            self.attrs.check_true(
                ':' in self.par,
                msg=f'@par should be two integers separated by ":", found "{self.par}"',
                clause='5.3.4.2')
