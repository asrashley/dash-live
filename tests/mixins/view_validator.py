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

import logging
import urllib.parse

from dashlive.server import models, routes
from dashlive.testcase.mixin import HideMixinsFilter
from dashlive.mpeg.dash.validator import DashValidator, RepresentationInfo, ValidatorOptions

class ViewsTestDashValidator(DashValidator):
    def __init__(self, http_client, mode, url, encrypted=False, xml=None, debug=False):
        opts = ValidatorOptions(strict=True, encrypted=encrypted)
        opts.log = logging.getLogger(__name__)
        opts.log.addFilter(HideMixinsFilter())
        if debug:
            opts.log.setLevel(logging.DEBUG)
        super().__init__(
            url=url,
            http_client=http_client,
            mode=mode,
            options=opts)
        self.representations = {}
        self.log.debug('Check manifest: %s', url)
        if xml is not None:
            self.load(xml)

    def get_representation_info(self, representation):
        try:
            return self.representations[representation.unique_id()]
        except KeyError:
            pass
        url = representation.init_seg_url()
        parts = urllib.parse.urlparse(url)
        self.log.debug('Trying to match %s using %s',
                       parts.path,
                       routes.routes["dash-media"].reTemplate.pattern)
        match = routes.routes["dash-media"].reTemplate.match(parts.path)
        if match is None:
            self.log.debug(
                'Tying to match %s using %s',
                parts.path,
                routes.routes["dash-od-media"].reTemplate.pattern)
            match = routes.routes["dash-od-media"].reTemplate.match(parts.path)
        if match is None:
            self.log.error('match %s %s', url, parts.path)
        self.assertIsNotNone(match, msg=f'Failed to find match for URL path "{parts.path}"')
        directory = match.group("stream")
        stream = models.Stream.get(directory=directory)
        self.assertIsNotNone(stream, msg=f'Failed to find stream {directory}')
        filename = match.group("filename")
        mf = models.MediaFile.get(name=filename)
        self.assertIsNotNone(mf, msg=f'Failed to find MediaFile {filename}')
        rep = mf.representation
        info = RepresentationInfo(
            num_segments=rep.num_media_segments, **rep.toJSON())
        self.set_representation_info(representation, info)
        return info

    def set_representation_info(self, representation, info):
        self.representations[representation.unique_id()] = info
