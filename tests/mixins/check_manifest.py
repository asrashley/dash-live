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

import datetime
from functools import wraps
import logging
import os
import urlparse

from testcase import HideMixinsFilter

import dash
import manifests
import models
import options
import routes


def add_url(method, url):
    @wraps(method)
    def tst_fn(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except AssertionError:
            print(url)
            raise
    return tst_fn

class ViewsTestDashValidator(dash.DashValidator):
    def __init__(self, app, mode, mpd, url):
        opts = dash.Options(strict=True)
        opts.log = logging.getLogger(__name__)
        opts.log.addFilter(HideMixinsFilter())
        # opts.log.setLevel(logging.DEBUG)
        super(
            ViewsTestDashValidator,
            self).__init__(
            url,
            app,
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
        info = dash.RepresentationInfo(
            num_segments=rep.num_segments, **rep.toJSON())
        self.set_representation_info(representation, info)
        return info

    def set_representation_info(self, representation, info):
        self.representations[representation.unique_id()] = info

class DashManifestCheckMixin(object):
    def _assert_true(self, result, a, b, msg, template):
        if not result:
            print(r'URL: {}'.format(self.current_url))
            if msg is not None:
                raise AssertionError(msg)
            raise AssertionError(template.format(a, b))

    def check_a_manifest_using_major_options(self, filename):
        """
        Exhaustive test of a manifest with every combination of options
        used by the manifest.
        This test might be _very_ slow (i.e. expect it to take several minutes)
        if the manifest uses lots of features.
        """
        self.check_a_manifest_using_all_options(filename, simplified=True)

    def check_a_manifest_using_all_options(self, filename, simplified=False):
        """
        Exhaustive test of a manifest with every combination of options
        used by the manifest.
        This test might be _very_ slow (i.e. expect it to take several minutes)
        if the manifest uses lots of features.
        """
        manifest = manifests.manifest[filename]
        cgi_options = manifest.get_cgi_options(simplified)
        self.setup_media()
        self.logoutCurrentUser()
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        # do a first pass check with no CGI options
        for mode in manifest.restrictions.get('mode', {'vod', 'live', 'odvod'}):
            url = self.from_uri(
                'dash-mpd-v3',
                manifest=filename,
                mode=mode,
                stream='bbb')
            self.check_manifest_url(url, mode)

        # do the exhaustive check of every option
        total_tests = 1
        count = 0
        for param in cgi_options:
            total_tests = total_tests * len(param[1])
        tested = set([url])
        indexes = [0] * len(cgi_options)
        done = False
        while not done:
            self.progress(count, total_tests)
            count += 1
            self.check_manifest_using_options(filename, cgi_options, indexes, tested)
            idx = 0
            while idx < len(cgi_options):
                indexes[idx] += 1
                if indexes[idx] < len(cgi_options[idx][1]):
                    break
                indexes[idx] = 0
                idx += 1
            if idx == len(cgi_options):
                done = True
        self.progress(total_tests, total_tests)

    def check_manifest_using_options(self, filename, cgi_options, indexes, tested):
        """
        Check one manifest using a specific combination of options
        :filename: the filename of the manifest
        :indexes: array for each option with the index for its setting
        :tested: set of URLs that have already been tested
        """
        params = {}
        mode = None
        for idx, option in enumerate(cgi_options):
            name, values = option
            value = values[indexes[idx]]
            if name == 'mode':
                mode = value[5:]
            elif value:
                params[name] = value
        self.assertIsNotNone(mode)
        self.assertIn(mode, options.supported_modes)
        # remove pointless combinations of options
        mft = manifests.manifest[filename]
        modes = mft.restrictions.get('mode', options.supported_modes)
        if mode not in modes:
            return
        if mode != "live":
            if "mup" in params:
                del params["mup"]
            if "time" in params:
                del params["time"]
        cgi = params.values()
        url = self.from_uri(
            'dash-mpd-v3',
            manifest=filename,
            mode=mode,
            stream='bbb')
        mpd_url = '{}?{}'.format(url, '&'.join(cgi))
        if mpd_url in tested:
            return
        tested.add(mpd_url)
        self.check_manifest_url(mpd_url, mode)

    def check_manifest_url(self, mpd_url, mode):
        try:
            self.current_url = mpd_url
            response = self.app.get(mpd_url)
            dv = ViewsTestDashValidator(self.app, mode, response.xml, mpd_url)
            dv.validate(depth=2)
            if mode != 'live':
                if dv.manifest.mediaPresentationDuration is None:
                    # duration must be specified in the Period
                    dur = datetime.timedelta(seconds=0)
                    for period in dv.manifest.periods:
                        self.assertIsNotNone(period.duration)
                        dur += period.duration
                    self.assertAlmostEqual(dur.total_seconds(), self.MEDIA_DURATION,
                                           delta=1.0)
                else:
                    self.assertAlmostEqual(dv.manifest.mediaPresentationDuration.total_seconds(),
                                           self.MEDIA_DURATION, delta=1.0)
            return dv
        finally:
            self.current_url = ''
