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
import os
import urlparse

from testcase.mixin import HideMixinsFilter

from dash_validator import DashValidator, RepresentationInfo, ValidatorOptions
from server import models, routes

class ViewsTestDashValidator(DashValidator):
    def __init__(self, http_client, mode, mpd, url, encrypted, debug=False):
        opts = ValidatorOptions(strict=True, encrypted=encrypted)
        opts.log = logging.getLogger(__name__)
        opts.log.addFilter(HideMixinsFilter())
        if debug:
            opts.log.setLevel(logging.DEBUG)
        super(
            ViewsTestDashValidator,
            self).__init__(
            url,
            http_client,
            mode=mode,
            options=opts)
        self.representations = {}
        self.log.debug('Check manifest: %s', url)

    def get_representation_info(self, representation):
        try:
            return self.representations[representation.unique_id()]
        except KeyError:
            pass
        url = representation.init_seg_url()
        parts = urlparse.urlparse(url)
        # self.log.debug('match %s %s', routes.routes["dash-media"].reTemplate.pattern, parts.path)
        match = routes.routes["dash-media"].reTemplate.match(parts.path)
        if match is None:
            # self.log.debug('match %s', routes.routes["dash-od-media"].reTemplate.pattern)
            match = routes.routes["dash-od-media"].reTemplate.match(parts.path)
        if match is None:
            self.log.error('match %s %s', url, parts.path)
        self.assertIsNotNone(match)
        filename = match.group("filename")
        name = filename + '.mp4'
        # self.log.debug("get_representation_info %s %s %s", url, filename, name)
        mf = models.MediaFile.query(models.MediaFile.name == name).get()
        if mf is None:
            filename = os.path.dirname(parts.path).split('/')[-1]
            name = filename + '.mp4'
            mf = models.MediaFile.query(models.MediaFile.name == name).get()
        self.assertIsNotNone(mf)
        rep = mf.representation
        info = RepresentationInfo(
            num_segments=rep.num_segments, **rep.toJSON())
        self.set_representation_info(representation, info)
        return info

    def set_representation_info(self, representation, info):
        self.representations[representation.unique_id()] = info
