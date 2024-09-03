#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import asyncio
import re
from typing import Any, ClassVar, Pattern

from lxml import etree as ET

from dashlive.utils.date_time import from_isodatetime

from .dash_element import DashElement

class Change(DashElement):
    attributes: ClassVar[list[tuple[str, Any, Any]]] = [
        ('sel', str, None),
    ]
    PATCH_NS_PREFIX: ClassVar[str] = f'{{{DashElement.xmlNamespaces["patch"]}}}'
    DASH_NS_PREFIX: ClassVar[str] = f'{{{DashElement.xmlNamespaces["dash"]}}}'
    FINAL_PATH_RE: ClassVar[Pattern] = re.compile(
        r'^(?P<element>\w+)\[(?P<addr>[^]]+)\]$')

    patch_type: str
    sel: str

    def __init__(self,
                 xml: ET.ElementBase,
                 parent: DashElement) -> None:
        super().__init__(xml, parent)
        self.patch_type = xml.tag
        self.xml = xml
        if self.patch_type.startswith(self.PATCH_NS_PREFIX):
            self.patch_type = xml.tag[len(self.PATCH_NS_PREFIX):]

    def children(self) -> list[DashElement]:
        return []

    def attribute_target(self) -> str | None:
        if self.sel is None:
            return None
        parts = self.sel.split('/')
        if not parts:
            return None
        if parts[-1][0] != '@':
            return None
        return parts[-1][1:]

    def apply_patch(self, dest: ET.ElementBase) -> bool:
        target = DashElement.xpath(dest, self.sel)
        if target is None or len(target) == 0:
            return False
        attr = self.attribute_target()
        elt: ET.ElementBase
        parent_sel = '/'.join(self.sel.split('/')[:-1])
        parent = DashElement.xpath(dest, parent_sel)[0]
        if attr:
            elt = parent
        else:
            elt = target[0]
        self.log.debug('change=%s sel=%s', self.patch_type, self.sel)
        if self.patch_type == 'add':
            if attr:
                self.elt.add_error('adding to an attribute not supported')
                return False
            for child in self.xml:
                elt.append(self.clone_to_dash_namespace(child))
        elif self.patch_type == 'replace':
            if attr:
                elt.set(attr, self.xml.text)
            else:
                for child in self.xml:
                    elt.addnext(self.clone_to_dash_namespace(child))
                parent.remove(elt)
        elif self.patch_type == 'remove':
            if attr:
                del elt.attrib[attr]
            else:
                parent.remove(target)
        return True

    async def validate(self) -> None:
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
        for part in self.sel.split('/'):
            if part in {'', 'MPD'}:
                continue
            match = self.FINAL_PATH_RE.match(part)
            if not match:
                if part[0] != '@':
                    self.attrs.add_error(
                        f'Elements must be addressed by position: {part} in {self.sel}',
                        clause='5.15.3.4')
                continue
            if match['element'] in {'Period', 'AdaptationSet', 'Representation', 'SubRepresentation'}:
                msg = (
                    f'{match["element"]} selector must be addressed by ID: ' +
                    f'{part} in {self.sel}')
                self.attrs.check_starts_with(
                    match['addr'], '@id=', msg=msg, clause='5.15.3.4')

    @classmethod
    def clone_to_dash_namespace(cls, elt: ET.ElementBase) -> ET.ElementBase:
        """
        Clone the specified element, converted from the MPD patch
        namespace to the DASH namespace.
        """
        tag = elt.tag.replace(cls.PATCH_NS_PREFIX, cls.DASH_NS_PREFIX)
        rv = ET.Element(tag, **elt.attrib)
        if elt.text:
            rv.text = elt.text
        for child in elt:
            rv.append(cls.clone_to_dash_namespace(child))
        return rv

class Patch(DashElement):
    attributes: ClassVar[list[tuple[str, Any, Any]]] = [
        ('mpdId', str, None),
        ('originalPublishTime', from_isodatetime, None),
        ('publishTime', from_isodatetime, None),
    ]

    changes: list[Change]
    mpdId: str
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

    def __str__(self) -> str:
        changes = [ch.sel for ch in self.changes]
        return (
            f'Patch({self.originalPublishTime.isoformat()} -> '
            f'{self.publishTime} changes={changes}')

    def children(self) -> list[DashElement]:
        return self.changes

    def print_patch_text(self) -> None:
        print(f'=== {self.url} ===')
        for idx, line in enumerate(self.xml_text, start=1):
            print(f'{idx:03d}: {line}')

    def apply_patch(self, dest: ET.ElementBase) -> bool:
        result = True
        for change in self.changes:
            r = change.apply_patch(dest)
            result = result and r
        return result

    async def validate(self) -> None:
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
        publish_time_change: Change | None = None
        futures = set()
        for child in self.changes:
            futures.add(child.validate())
            if child.sel == '/MPD/@publishTime':
                publish_time_change = child
        await asyncio.gather(*futures)
        if not self.elt.check_not_none(
                publish_time_change,
                msg='The Patch must contain a replace element for MPD@publishTime'):
            return
        try:
            new_publish_time = from_isodatetime(publish_time_change.xml.text)
            self.elt.check_greater_than(
                new_publish_time, self.mpd.publishTime,
                msg='Patched MPD@publishTime must be greater than current publishTime')
        except ValueError as err:
            self.elt.add_error(
                f'/MPD/@publishTime patch must contain a valid ISO date-time: {err}')
