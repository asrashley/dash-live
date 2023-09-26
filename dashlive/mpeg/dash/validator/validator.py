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

import io
import json
import time
from typing import Optional

from lxml import etree as ET

from dashlive.mpeg.dash.representation import Representation as ServerRepresentation

from .dash_element import DashElement
from .manifest import Manifest
from .options import ValidatorOptions

class DashValidator(DashElement):
    def __init__(self, url, http_client,
                 mode: str | None = None,
                 options: ValidatorOptions | None = None,
                 xml: Optional[ET.Element] = None) -> None:
        DashElement.init_xml_namespaces()
        super().__init__(None, parent=None, options=options)
        self.http = http_client
        self.baseurl = self.url = url
        self.options = options if options is not None else ValidatorOptions()
        self.mode = mode
        self.validator = self
        self.xml = xml
        self.manifest: Manifest | None = None
        self.manifest_text: list[tuple[int, str]] = []
        self.prev_manifest = None
        self.pool = options.pool
        self.prefetch_done = False
        if xml is not None:
            self.progress.reset(1)
            self.manifest = Manifest(self, self.url, self.mode, self.xml)
            self.manifest.prefetch_media_info()
            self.prefetch_done = True

    def load(self, xml=None) -> bool:
        self.progress.reset(1)
        self.prefetch_done = False
        self.prev_manifest = self.manifest
        self.xml = xml
        if self.xml is None:
            self.fetch_manifest()
        if self.mode is None:
            if self.xml.get("type") == "dynamic":
                self.mode = 'live'
            elif "urn:mpeg:dash:profile:isoff-on-demand:2011" in self.xml.get('profiles'):
                self.mode = 'odvod'
            else:
                self.mode = 'vod'
        self.manifest = Manifest(self, self.url, self.mode, self.xml)
        return True

    def prefetch_media_info(self) -> None:
        if self.prefetch_done:
            return
        self.log.info('Prefetching media files required before validation can start')
        self.progress.text('Prefetching media files')
        self.manifest.prefetch_media_info()
        self.prefetch_done = True

    def get_manifest_lines(self) -> list[str]:
        return self.manifest_text

    def fetch_manifest(self) -> bool:
        self.progress.text(self.url)
        result = self.http.get(self.url)
        if not self.elt.check_equal(
                result.status_code, 200,
                msg=f'Failed to load manifest: {result.status_code} {self.url}'):
            return False
        # print(result.text)
        xml = ET.parse(io.BytesIO(result.get_data(as_text=False)))
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

    def validate(self, depth=-1) -> bool:
        if self.xml is None:
            if not self.load():
                return False
        self.prefetch_media_info()
        self.progress.reset(self.manifest.num_tests(depth))
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
                age, 5 * self.manifest.minimumUpdatePeriod,
                fmt.format(self.manifest.minimumUpdatePeriod, age.total_seconds()))
        self.manifest.validate(depth=depth)
        if self.pool:
            for err in self.pool.wait_for_completion():
                self.elt.add_error(f'Exception: {err}')
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
            with open(filename, 'wt') as dest:
                json.dump(config, dest, indent=2)
        return self.has_errors()

    def get_json_script_filename(self) -> str:
        return self.output_filename(
            default=None, bandwidth=None, filename=f'{self.options.prefix}.json')

    def children(self) -> list[DashElement]:
        if self.manifest is None:
            return []
        return [self.manifest]

    def save_manifest(self, filename=None):
        if self.options.dest:
            filename = self.output_filename(
                'manifest.mpd', bandwidth=None, filename=filename, makedirs=True)
            ET.ElementTree(self.xml).write(filename, xml_declaration=True)
        else:
            print(ET.tostring(self.xml))

    def sleep(self):
        self.checkEqual(self.mode, 'live')
        self.checkIsNotNone(self.manifest)
        dur = max(self.manifest.minimumUpdatePeriod.seconds, 1)
        self.log.info('Wait %d seconds', dur)
        time.sleep(dur)

    def set_representation_info(self, info: ServerRepresentation):
        if self.manifest is None:
            return
        self.manifest.set_representation_info(info)
