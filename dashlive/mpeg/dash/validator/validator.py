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

from abc import abstractmethod
import io
import json
import time

from lxml import etree as ET

from .dash_element import DashElement
from .manifest import Manifest
from .options import ValidatorOptions
from .representation import Representation
from .representation_info import RepresentationInfo

class DashValidator(DashElement):
    def __init__(self, url, http_client,
                 mode: str | None = None, options: ValidatorOptions | None = None,
                 xml: str | None = None) -> None:
        DashElement.init_xml_namespaces()
        super().__init__(None, parent=None, options=options)
        self.http = http_client
        self.baseurl = self.url = url
        self.options = options if options is not None else ValidatorOptions()
        self.mode = mode
        self.validator = self
        self.xml = xml
        self.manifest = None
        self.manifest_text: list[tuple[int, str]] = []
        self.prev_manifest = None
        if xml is not None:
            self.manifest = Manifest(self, self.url, self.mode, self.xml)

    def load(self, xml=None) -> bool:
        self.prev_manifest = self.manifest
        self.xml = xml
        if self.xml is None:
            result = self.http.get(self.url)
            if not self.elt.check_equal(
                    result.status_code, 200,
                    msg=f'Failed to load manifest: {result.status_code} {self.url}'):
                return False
            # print(result.text)
            xml = ET.parse(io.BytesIO(result.get_data(as_text=False)))
            self.manifest_text = []
            for line in io.StringIO(result.get_data(as_text=True)):
                self.manifest_text.append(line[:-1])
            if self.options.pretty:
                encoding = xml.docinfo.encoding
                pp_txt = ET.tostring(xml, pretty_print=True, xml_declaration=True,
                                     encoding=encoding)
                xml = ET.parse(io.BytesIO(pp_txt))
                self.manifest_text = []
                for line in io.StringIO(str(pp_txt, encoding)):
                    self.manifest_text.append(line[:-1])
            self.xml = xml.getroot()
        if self.mode is None:
            if self.xml.get("type") == "dynamic":
                self.mode = 'live'
            elif "urn:mpeg:dash:profile:isoff-on-demand:2011" in self.xml.get('profiles'):
                self.mode = 'odvod'
            else:
                self.mode = 'vod'
        self.manifest = Manifest(self, self.url, self.mode, self.xml)
        return True

    def get_manifest_lines(self) -> list[str]:
        return self.manifest_text

    def validate(self, depth=-1) -> bool:
        if self.xml is None:
            if not self.load():
                return False
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
        if self.options.save and self.options.prefix:
            kids = set()
            for p in self.manifest.periods:
                for a in p.adaptation_sets:
                    if a.default_KID is not None:
                        kids.add(a.default_KID)
            config = {
                'keys': [{'computed': True, 'kid': kid} for kid in list(kids)],
                'streams': [{
                    'directory': self.options.prefix,
                    'title': self.url,
                    'files': list(self.manifest.filenames)
                }],
            }
            filename = self.output_filename(
                default=None, bandwidth=None, filename=f'{self.options.prefix}.json')
            with open(filename, 'wt') as dest:
                json.dump(config, dest, indent=2)
        return self.has_errors()

    def children(self) -> list[DashElement]:
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

    @abstractmethod
    def get_representation_info(self, rep: Representation)  -> RepresentationInfo:
        """Get the Representation object for the specified media URL.
        The returned object must have the following attributes:
        * encrypted: bool         - Is AdaptationSet encrypted ?
        * ivsize: int             - IV size in bytes (8 or 16) (N/A if encrypted==False)
        * timescale: int          - The timescale units for the AdaptationSet
        * num_segments: int       - The number of segments in the stream (VOD only)
        * segments: List[Segment] - Information about each segment (optional)
        """
        raise Exception("Not implemented")

    @abstractmethod
    def set_representation_info(self, rep: Representation, info: RepresentationInfo):
        raise Exception("Not implemented")
