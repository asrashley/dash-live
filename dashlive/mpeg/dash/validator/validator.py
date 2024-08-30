#############################################################################
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import asyncio
import datetime
import io
import json
from typing import Optional

from lxml import etree as ET

from dashlive.mpeg.dash.representation import Representation as ServerRepresentation

from .dash_element import DashElement
from .http_client import HttpClient
from .manifest import Manifest
from .options import ValidatorOptions

class DashValidator(DashElement):
    def __init__(self, url: str, http_client: HttpClient,
                 mode: str | None = None,
                 options: ValidatorOptions | None = None) -> None:
        DashElement.init_xml_namespaces()
        super().__init__(None, parent=None, options=options)
        self.http = http_client
        self.baseurl = self.url = url
        self.options = options if options is not None else ValidatorOptions()
        self.mode = mode
        self.validator = self
        self.xml = None
        self.manifest: Manifest | None = None
        self.manifest_text: list[tuple[int, str]] = []
        self.prev_manifest = None
        self.pool = options.pool

    async def load(self,
                   xml: Optional[ET.ElementBase] = None,
                   data: Optional[bytes] = None) -> bool:
        self.progress.reset(1)
        self.prev_manifest = None
        self.xml = xml

        if self.xml is None and data:
            doc = ET.parse(io.BytesIO(data))
            self.xml = doc.getroot()
            self.manifest_text = []
            encoding = doc.docinfo.encoding
            for line in io.StringIO(str(data, encoding)):
                self.manifest_text.append(line.rstrip())

        if self.xml is None:
            if not await self.fetch_manifest():
                return False

        if self.mode is None:
            if self.xml.get("type") == "dynamic":
                self.mode = 'live'
            elif "urn:mpeg:dash:profile:isoff-on-demand:2011" in self.xml.get('profiles'):
                self.mode = 'odvod'
            else:
                self.mode = 'vod'
        self.manifest = Manifest(self, self.url, self.mode, self.xml)
        return True

    async def refresh(self) -> bool:
        """
        Reload a live manifest.
        This will copy across some information from the previous manifest into
        the new one.
        """
        if self.mode != 'live':
            self.log.debug('Not a live stream, no need to reload manifest')
            return True
        self.prev_manifest = self.manifest
        if not await self.fetch_manifest():
            return False
        self.manifest = Manifest(self, self.url, self.mode, self.xml)
        return await self.manifest.merge_previous_element(self.prev_manifest)

    def finished(self) -> bool:
        if self.manifest is None:
            return False
        return self.manifest.finished()

    async def prefetch_media_info(self) -> bool:
        self.log.info('Prefetching media files required before validation can start')
        self.progress.text('Prefetching media files')
        return await self.manifest.prefetch_media_info()

    def get_manifest_lines(self) -> list[str]:
        return self.manifest_text

    def get_codecs(self) -> set[str]:
        if self.manifest is None:
            return set()
        return self.manifest.get_codecs()

    async def fetch_manifest(self) -> bool:
        self.progress.text(self.url)
        self.log.debug('Fetch manifest %s', self.url)
        result = await self.http.get(self.url)
        if not self.elt.check_equal(
                result.status_code, 200,
                msg=f'Failed to load manifest: {result.status_code} {self.url}'):
            return False
        parser = ET.XMLParser(remove_blank_text=self.options.pretty)
        xml = ET.parse(
            io.BytesIO(result.get_data(as_text=False)), parser)
        self.manifest_text = []
        for line in io.StringIO(result.get_data(as_text=True)):
            self.manifest_text.append(line.rstrip())
        if self.options.pretty:
            encoding = xml.docinfo.encoding
            pp_txt = ET.tostring(xml, pretty_print=True, xml_declaration=True,
                                 encoding=encoding)
            xml = ET.parse(io.BytesIO(pp_txt))
            self.manifest_text = []
            for line in io.StringIO(str(pp_txt, encoding)):
                self.manifest_text.append(line.rstrip())
        self.xml = xml.getroot()
        self.progress.text('')
        return True

    async def validate(self) -> bool:
        if self.xml is None:
            if not await self.load():
                return False
        await self.prefetch_media_info()
        self.progress.reset(self.manifest.num_tests())
        if self.options.save:
            self.save_manifest()
        if self.mode == 'live' and self.prev_manifest is not None:
            self.attrs.check_equal(
                self.prev_manifest.availabilityStartTime, self.manifest.availabilityStartTime,
                template=r'availabilityStartTime has changed from {} to {}')
            age = self.manifest.publishTime - self.prev_manifest.publishTime
            fmt = (r'Manifest should have updated by now. minimumUpdatePeriod is {0} but ' +
                   r'manifest has not been updated for {1} seconds')
            self.attrs.check_less_than(
                age, 3 * self.manifest.minimumUpdatePeriod,
                fmt.format(self.manifest.minimumUpdatePeriod, age.total_seconds()))
        await self.manifest.validate()
        if self.options.save and self.options.prefix:
            kids = set()
            for p in self.manifest.periods:
                for a in p.adaptation_sets:
                    if a.default_KID is not None:
                        kids.add(a.default_KID)
            if self.options.title is None:
                title = self.url
            else:
                title = self.options.title
            config = {
                'keys': [{'computed': True, 'kid': kid} for kid in list(kids)],
                'streams': [{
                    'directory': self.options.prefix,
                    'title': title,
                    'files': list(self.manifest.filenames)
                }],
            }
            filename = self.get_json_script_filename()
            self.log.debug('Creating json file %s', filename)
            with open(filename, 'wt', encoding='ascii') as dest:
                json.dump(config, dest, indent=2)
        return self.has_errors()

    def print_manifest_text(self) -> None:
        print(f'=== {self.url} ===')
        for idx, line in enumerate(self.manifest_text, start=1):
            print(f'{idx:03d}: {line}')
        for patch in self.manifest.patches:
            patch.print_patch_text()

    def get_json_script_filename(self) -> str:
        return self.output_filename(
            default=None, bandwidth=None,
            filename=f'{self.options.prefix}.json')

    def children(self) -> list[DashElement]:
        if self.manifest is None:
            return []
        return [self.manifest]

    def save_manifest(self, filename=None):
        if self.options.dest:
            filename = self.output_filename(
                'manifest.mpd', bandwidth=None, filename=filename,
                makedirs=True)
            ET.ElementTree(self.xml).write(
                filename, xml_declaration=True, pretty_print=True)
        else:
            print(ET.tostring(self.xml, pretty_print=True))

    async def sleep(self):
        if not self.elt.check_equal(self.mode, 'live'):
            return
        if not self.elt.check_not_none(self.manifest):
            return
        next_refresh = self.manifest.publishTime + self.manifest.minimumUpdatePeriod
        self.log.debug(
            'publishTime=%s minimumUpdatePeriod=%s nextUpdate=%s',
            self.manifest.publishTime, self.manifest.minimumUpdatePeriod,
            next_refresh)
        diff = next_refresh - self.manifest.now()
        self.log.info('Diff = %s seconds', diff.total_seconds())
        if diff > datetime.timedelta(seconds=0):
            self.log.info('Wait %s', diff)
            await asyncio.sleep(diff.total_seconds())

    def set_representation_info(self, info: ServerRepresentation):
        if self.manifest is None:
            return
        self.manifest.set_representation_info(info)
