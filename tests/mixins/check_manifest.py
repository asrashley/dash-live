############################################################################
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

from __future__ import print_function
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()
from builtins import zip
from builtins import object
from contextlib import contextmanager
import datetime
from functools import wraps
import io
import os
import urllib.parse

import flask
from lxml import etree as ET

from dashlive.server import manifests, models, cgi_options
from dashlive.server.requesthandler.manifest_requests import ServeManifest

from .view_validator import ViewsTestDashValidator

def add_url(method, url):
    @wraps(method)
    def tst_fn(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except AssertionError:
            print(url)
            raise
    return tst_fn

class MockServeManifest(ServeManifest):
    def __init__(self, request, **kwargs):
        super(MockServeManifest, self).__init__(**kwargs)
        self.request = request

    def is_https_request(self):
        return False

    def uri_for(self, route, **kwargs):
        if route == 'time':
            return r'{0}/time/{1}'.format(self.request.host_url, kwargs['format'])
        if route == 'clearkey':
            return r'{0}/clearkey/'.format(self.request.host_url)
        raise ValueError(r'Unsupported route name: {0}'.format(route))

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

    def check_a_manifest_using_all_options(self, filename, simplified=False, with_subs=False):
        """
        Exhaustive test of a manifest with every combination of options
        used by the manifest.
        This test might be _very_ slow (i.e. expect it to take several minutes)
        if the manifest uses lots of features.
        """
        manifest = manifests.manifest[filename]
        options = manifest.get_cgi_options(simplified)
        self.setup_media(with_subs=with_subs)
        self.logout_user()
        self.assertGreaterThan(models.MediaFile.count(), 0)
        # do a first pass check with no CGI options
        for mode in manifest.restrictions.get('mode', {'vod', 'live', 'odvod'}):
            url = flask.url_for(
                'dash-mpd-v3',
                manifest=filename,
                mode=mode,
                stream=self.FIXTURES_PATH.name)
            self.check_manifest_url(url, mode, encrypted=False)

        # do the exhaustive check of every option
        total_tests = 1
        count = 0
        for param in options:
            total_tests = total_tests * len(param[1])
        tested = set([url])
        indexes = [0] * len(options)
        done = False
        while not done:
            self.progress(count, total_tests)
            count += 1
            self.check_manifest_using_options(filename, options, indexes, tested)
            idx = 0
            while idx < len(options):
                indexes[idx] += 1
                if indexes[idx] < len(options[idx][1]):
                    break
                indexes[idx] = 0
                idx += 1
            if idx == len(options):
                done = True
        self.progress(total_tests, total_tests)

    def check_manifest_using_options(self, filename, options, indexes, tested):
        """
        Check one manifest using a specific combination of options
        :filename: the filename of the manifest
        :indexes: array for each option with the index for its setting
        :tested: set of URLs that have already been tested
        """
        params = {}
        mode = None
        for idx, option in enumerate(options):
            name, values = option
            value = values[indexes[idx]]
            if name == 'mode':
                mode = value[5:]
            elif value:
                params[name] = value
        self.assertIsNotNone(mode)
        self.assertIn(mode, cgi_options.supported_modes)
        # remove pointless combinations of options
        mft = manifests.manifest[filename]
        modes = mft.restrictions.get('mode', cgi_options.supported_modes)
        if mode not in modes:
            return
        if mode != "live":
            if "mup" in params:
                del params["mup"]
            if "time" in params:
                del params["time"]
        encrypted = params.get("drm", "drm=none") != "drm=none"
        cgi = list(params.values())
        url = flask.url_for(
            'dash-mpd-v3',
            manifest=filename,
            mode=mode,
            stream=self.FIXTURES_PATH.name)
        mpd_url = '{}?{}'.format(url, '&'.join(cgi))
        if mpd_url in tested:
            return
        tested.add(mpd_url)
        self.check_manifest_url(mpd_url, mode, encrypted)

    def check_manifest_url(self, mpd_url, mode, encrypted, check_head=False):
        """
        Test one manifest for validity
        """
        response = None
        try:
            self.current_url = mpd_url
            response = self.client.get(mpd_url)
            if response.status_code == 302:
                # Handle redirect request
                mpd_url = response.headers['Location']
                self.current_url = mpd_url
                response = self.client.get(mpd_url)
            # print(response.text)
            self.assertEqual(response.status_code, 200)
            xml = ET.parse(io.BytesIO(response.get_data(as_text=False)))
            dv = ViewsTestDashValidator(
                http_client=self.client, mode=mode, xml=xml.getroot(),
                url=mpd_url, encrypted=encrypted)
            dv.validate(depth=3)
            if check_head:
                head = self.client.head(mpd_url)
            if mode != 'live':
                if check_head:
                    self.assertEqual(
                        head.headers['Content-Length'],
                        response.headers['Content-Length'])
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
        except AssertionError:
            if response is not None:
                print(response.text)
            raise
        finally:
            self.current_url = ''

    @contextmanager
    def create_mock_request_context(self, url: str, stream: models.Stream,
                                    method: str = 'GET'):
        abs_url = urllib.parse.urljoin('http://unit.test/', url)
        parsed = urllib.parse.urlparse(abs_url)
        with self.app.test_request_context(url, method='GET') as context:
            flask.g.stream = stream
            flask.request.url = abs_url
            flask.request.scheme = parsed.scheme
            flask.request.remote_addr = '127.0.0.1'
            flask.request.host = r'unit.test'
            flask.request.host_url = r'http://unit.test/'
            yield context

    def check_generated_manifest_against_fixture(self, mpd_filename, mode, **kwargs):
        """
        Check a freshly generated manifest against a "known good" previous example
        """
        self.setup_media()
        self.init_xml_namespaces()
        url = flask.url_for(
            "dash-mpd-v3",
            mode=mode,
            stream=self.FIXTURES_PATH.name,
            manifest=mpd_filename,
            **kwargs)
        stream = models.Stream.get(directory=self.FIXTURES_PATH.name)
        self.assertIsNotNone(stream)
        # with self.app.test_request_context(url, method='GET'):
        with self.create_mock_request_context(url, stream):
            context = self.generate_manifest_context(
                mpd_filename, mode=mode, stream=stream, **kwargs)
            text = flask.render_template(mpd_filename, **context)
        encrypted = kwargs.get('drm', 'none') != 'none'
        fixture = self.fixture_filename(mpd_filename, mode, encrypted)
        expected = ET.parse(fixture).getroot()
        actual = ET.fromstring(bytes(text, 'utf-8'))
        self.assertXmlEqual(expected, actual)

    def generate_manifest_context(self, mpd_filename, mode, stream, **kwargs):
        mock = MockServeManifest(flask.request)
        context = mock.calculate_dash_params(mpd_url=mpd_filename, mode=mode)
        encrypted = kwargs.get('drm', 'none') != 'none'
        if encrypted:
            kids = set()
            for period in context['periods']:
                kids.update(period.key_ids())
            if not kids:
                keys = models.Key.all_as_dict()
            else:
                keys = models.Key.get_kids(kids)
            context["DRM"] = mock.generate_drm_dict(stream, keys)
        context['remote_addr'] = mock.request.remote_addr
        context['request_uri'] = mock.request.url
        context['title'] = stream.title
        return context

    @staticmethod
    def fixture_filename(mpd_name, mode, encrypted):
        """returns absolute file path of the given fixture"""
        name, ext = os.path.splitext(mpd_name)
        enc = '_enc' if encrypted else ''
        filename = r'{0}_{1}{2}{3}'.format(name, mode, enc, ext)
        return os.path.join(os.path.dirname(__file__), '..', 'fixtures', filename)

    xmlNamespaces = {
        'cenc': 'urn:mpeg:cenc:2013',
        'dash': 'urn:mpeg:dash:schema:mpd:2011',
        'mspr': 'urn:microsoft:playready',
        'scte35': "http://www.scte.org/schemas/35/2016",
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'prh': 'http://schemas.microsoft.com/DRM/2007/03/PlayReadyHeader',
    }

    @classmethod
    def init_xml_namespaces(clz):
        for prefix, url in clz.xmlNamespaces.items():
            ET.register_namespace(prefix, url)

    def assertXmlTextEqual(self, expected, actual, msg=None):
        if expected is not None:
            expected = expected.strip()
            if expected == "":
                expected = None
        if actual is not None:
            actual = actual.strip()
            if actual == "":
                actual = None
        msg = r'{0}: Expected "{1}" got "{2}"'.format(msg, expected, actual)
        self.assertEqual(expected, actual, msg=msg)

    def assertXmlEqual(self, expected, actual, index=0, msg=None, strict=False):
        tag = ET.QName(expected.tag)
        if msg is None:
            prefix = tag.localname
        else:
            prefix = r'{0}/{1}'.format(msg, tag.localname)
        if index > 0:
            prefix += r'[{0:d}]'.format(index)
        self.assertEqual(
            expected.tag, actual.tag,
            msg=r'{0}: Expected "{1}" got "{2}"'.format(prefix, expected.tag, actual.tag))
        self.assertXmlTextEqual(
            expected.text, actual.text,
            msg='{0}: text does not match'.format(prefix))
        self.assertXmlTextEqual(
            expected.tail, actual.tail,
            msg='{0}: tail does not match'.format(prefix))

        for name, exp_value in expected.attrib.items():
            key_name = '{0}@{1}'.format(prefix, name)
            self.assertIn(name, actual.attrib, msg='Missing attribute {}'.format(key_name))
            act_value = actual.attrib[name]
            self.assertEqual(
                exp_value, act_value,
                msg='attribute {0} should be "{1}" but was "{2}"'.format(
                    key_name, exp_value, act_value))
        counts = {}
        for exp, act in zip(expected, actual):
            idx = counts.get(exp.tag, 0)
            self.assertXmlEqual(exp, act, msg=prefix, index=idx)
            counts[exp.tag] = idx + 1
