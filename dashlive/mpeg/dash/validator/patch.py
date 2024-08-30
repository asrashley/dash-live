#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from typing import Any, ClassVar

from lxml import etree as ET

from dashlive.utils.date_time import from_isodatetime

from .dash_element import DashElement

class Change(DashElement):
    attributes: ClassVar[list[tuple[str, Any, Any]]] = [
        ('sel', str, None),
    ]

    patch_type: str
    sel: str

    def __init__(self,
                 xml: ET.ElementBase,
                 parent: DashElement) -> None:
        super().__init__(xml, parent)
        prefix = f'{{{self.xmlNamespaces["patch"]}}}'
        self.patch_type = xml.tag
        if self.patch_type.startswith(prefix):
            self.patch_type = xml.tag[len(prefix):]

    def children(self) -> list[DashElement]:
        return []

    def validate(self) -> None:
        self.elt.check_includes(
            ['add', 'replace', 'remove'],
            self.patch_type,
            msg=f'Unexpected Patch element {self.patch_type}',
            clause='5.15.3')
        if not self.attrs.check_not_none(
                self.sel,
                'sel attribute is mandatory', clause='5.15.3.4'):
            return
        xml = self.mpd.parent.xml
        target = self.xpath(xml, self.sel)
        if target is None or len(target) == 0:
            self.attrs.add_error(
                f'Failed to find manifest node "{self.sel}"')
            return
        self.attrs.check_equal(
            len(target), 1,
            msg='XPath must only select a single node',
            clause='5.15.3.4')


class Patch(DashElement):
    attributes: ClassVar[list[tuple[str, Any, Any]]] = [
        ('mpdId', str, None),
        ('originalPublishTime', from_isodatetime, None),
        ('publishTime', from_isodatetime, None),
    ]

    changes: list[Change]
    xml_text: list[str]
    url: str

    def __init__(self,
                 xml: ET.ElementBase,
                 parent: DashElement,
                 url: str,
                 xml_text: list[str]) -> None:
        super().__init__(xml, parent)
        self.url = url
        self.xml_text = xml_text
        self.changes = [Change(elt, self) for elt in xml]
        tag = f'{{{self.xmlNamespaces["patch"]}}}Patch'
        self.elt.check_equal(
            xml.tag, tag,
            msg=f'must have a Patch element as toplevel element not {xml.tag}')

    def children(self) -> list[DashElement]:
        return self.changes

    def print_patch_text(self) -> None:
        print(f'=== {self.url} ===')
        for idx, line in enumerate(self.xml_text, start=1):
            print(f'{idx:03d}: {line}')

    def validate(self) -> None:
        self.attrs.check_not_none(
            self.mpdId,
            msg='Patch@mpdId is a mandatory attribute',
            clause='5.15.3.2')
        self.attrs.check_equal(
            self.mpdId,
            self.mpd.id,
            msg='Patch@mpdId must match MPD@id',
            clause='5.15.5')
        self.attrs.check_not_none(
            self.publishTime,
            msg='Patch@publishTime is a mandatory attribute',
            clause='5.15.3.2')
        self.attrs.check_not_none(
            self.originalPublishTime,
            msg='Patch@originalPublishTime is a mandatory attribute',
            clause='5.15.3.2')
        self.attrs.check_equal(
            self.originalPublishTime,
            self.mpd.publishTime,
            msg='Patch@originalPublishTime must match MPD@publishTime',
            clause='5.15.5')
        self.attrs.check_greater_than(
            self.publishTime,
            self.originalPublishTime,
            msg='publishTime must be greater than originalPublishTime',
            clause='5.15.5')
        for child in self.changes:
            child.validate()
