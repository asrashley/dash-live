#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import io
from typing import Any, ClassVar
import urllib.parse

from lxml import etree as ET

from .dash_element import DashElement
from .patch import Patch
from .validation_flag import ValidationFlag

class PatchLocation(DashElement):
    attributes: ClassVar[list[tuple[str, Any, Any]]] = [
        ('ttl', int, None),
    ]

    url: str
    patch: Patch | None

    def __init__(self,
                 xml: ET.ElementBase,
                 parent: DashElement | None) -> None:
        super().__init__(xml, parent)
        self.url = xml.text
        self.patch = None

    def children(self) -> list[DashElement]:
        if self.patch:
            return [self.patch]
        return []

    async def validate(self) -> None:
        if ValidationFlag.MANIFEST not in self.options.verify:
            return
        if not self.elt.check_not_none(
                self.url,
                'PatchLocation must contain a URL',
                clause='5.15.2'):
            return
        try:
            parsed = urllib.parse.urlparse(self.url, scheme='http')
            if not self.elt.check_includes(
                    ['http', 'https'],
                    parsed.scheme.lower(),
                    msg=f'Expected HTTP or HTTPS for Patch URL, got "{self.url}"'):
                return
            mpd = self.mpd
            elapsed = mpd.now() - mpd.publishTime
            if (
                    self.patch is None and
                    mpd.minimumUpdatePeriod is not None and
                    elapsed >= mpd.minimumUpdatePeriod):
                if not await self.load():
                    self.elt.add_error('Failed to load patch')
                    return
            if self.patch:
                await self.patch.validate()
        except ValueError as err:
            self.elt.add_error(
                f'Failed to parse PatchLocation URL: {err}',
                clause='5.15')
            return

    async def load(self) -> bool:
        if not self.elt.check_not_none(
                self.url, msg='URL of PatchLocation is missing'):
            return False
        self.log.debug('Fetching MPD patch: %s', self.url)
        response = await self.http.get(self.url)
        if not self.elt.check_equal(
                response.status_code, 200,
                msg=f'Failed to load patch: {response.status_code}: {self.url}'):
            return False
        try:
            async with self.pool.group() as tg:
                body = response.get_data(as_text=False)
                if self.options.save:
                    tg.submit(self.save, body)
                tg.submit(self.parse_body, body)
        except Exception as exc:
            self.elt.add_error(f'Failed to load patch: {exc}')
            self.log.error('Failed to load patch: %s', exc)
            return False
        return True

    def print_patch_text(self) -> None:
        if self.patch is not None:
            self.patch.print_patch_text()
        else:
            print(f'== Patch {self.url} has not been fetched ==')

    def save(self, body: bytes) -> None:
        if self.parent.id:
            default = f'patch-{self.parent.id}'
        else:
            default = 'patch'
        filename = self.output_filename(
            default=default, bandwidth=None,
            prefix=self.options.prefix, elt_id=self.parent.id,
            makedirs=True)
        self.log.debug('saving Patch file: %s', filename)
        with self.open_file(filename, self.options) as dest:
            dest.write(body)

    def parse_body(self, body: bytes) -> None:
        parser = ET.XMLParser(remove_blank_text=self.options.pretty)
        xml = ET.parse(io.BytesIO(body), parser)
        xml_text: list[str] = []
        encoding = xml.docinfo.encoding
        if self.options.pretty:
            pp_txt = ET.tostring(
                xml, pretty_print=True, xml_declaration=True,
                encoding=encoding)
            xml = ET.parse(io.BytesIO(pp_txt))
            for line in io.StringIO(str(pp_txt, encoding)):
                xml_text.append(line.rstrip())
        else:
            for line in io.StringIO(str(body, encoding)):
                xml_text.append(line.rstrip())
        self.patch = Patch(xml.getroot(), self, self.url, xml_text)
