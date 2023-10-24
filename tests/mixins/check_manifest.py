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

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import datetime
from functools import wraps
import io
import os
import logging
from typing import AbstractSet
import urllib.parse

import flask
from lxml import etree as ET

from dashlive.mpeg.dash.profiles import primary_profiles
from dashlive.mpeg.dash.validator import ConcurrentWorkerPool
from dashlive.server import manifests, models
from dashlive.server.options.container import OptionsContainer
from dashlive.server.options.repository import OptionsRepository
from dashlive.server.requesthandler.manifest_requests import ServeManifest

from .view_validator import ViewsTestDashValidator

def add_url(method, url):
    @wraps(method)
    def tst_fn(self, *args, **kwargs):
        try:
            self.log_context.add_item('url', url)
            return method(self, *args, **kwargs)
        except AssertionError:
            print(f'URL="{url}"')
            raise
        finally:
            self.log_context.add_item('url', '')
    return tst_fn

class MockServeManifest(ServeManifest):
    def __init__(self, request, **kwargs):
        super().__init__(**kwargs)
        self.request = request

    def is_https_request(self):
        return False

    def uri_for(self, route, **kwargs):
        if route == 'time':
            return r'{}/time/{}'.format(self.request.host_url, kwargs['format'])
        if route == 'clearkey':
            return fr'{self.request.host_url}/clearkey/'
        raise ValueError(fr'Unsupported route name: {route}')

class DashManifestCheckMixin:
    async def check_a_manifest_using_major_options(self, filename: str, mode: str) -> None:
        """
        Exhaustive test of a manifest with every combination of options
        used by the manifest.
        This test might be _very_ slow (i.e. expect it to take several minutes)
        if the manifest uses lots of features.
        """
        await self.check_a_manifest_using_all_options(filename, mode, simplified=True)

    async def check_a_manifest_using_all_options(
            self,
            filename: str,
            mode: str,
            simplified: bool = False,
            with_subs: bool = False,
            only: AbstractSet | None = None,
            extras: list[tuple] | None = None) -> None:
        """
        Exhaustive test of a manifest with every combination of options
        used by the manifest.
        This test might be _very_ slow (i.e. expect it to take several minutes)
        if the manifest uses lots of features.
        """
        manifest = manifests.manifest[filename]
        self.assertIn(mode, primary_profiles)
        modes = manifest.restrictions.get('mode', primary_profiles.keys())
        self.assertIn(mode, modes)
        self.setup_media(with_subs=with_subs)
        self.logout_user()
        self.assertGreaterThan(models.MediaFile.count(), 0)
        # do a first pass check with no CGI options
        url = flask.url_for(
            'dash-mpd-v3',
            manifest=filename,
            mode=mode,
            stream=self.FIXTURES_PATH.name)
        await self.check_manifest_url(url, mode, encrypted=False)

        # do the exhaustive check of every option
        options = manifest.get_cgi_query_combinations(
            mode=mode, simplified=simplified, only=only, extras=extras)
        total_tests = len(options)
        count = 0
        logging.debug('total %s tests for "%s" = %d', mode, filename, total_tests)
        for query in options:
            self.progress(count, total_tests)
            count += 1
            await self.check_manifest_using_options(mode, url, query)
        self.progress(total_tests, total_tests)

    async def check_manifest_using_options(self, mode: str, url: str, query: str) -> None:
        """
        Check one manifest using a specific combination of options
        :mode: operating mode
        :filename: the filename of the manifest
        :query: the query string
        """
        mpd_url = f'{url}{query}'
        clear = ('drm=none' in query) or ('drm' not in query)
        await self.check_manifest_url(mpd_url, mode, not clear)

    async def check_manifest_url(self, mpd_url: str, mode: str, encrypted: bool,
                           check_head=False) -> ViewsTestDashValidator:
        """
        Test one manifest for validity (wrapped in context of MPD url)
        """
        try:
            self.log_context.add_item('url', mpd_url)
            return await self.do_check_manifest_url(mpd_url, mode, encrypted, check_head)
        finally:
            del self.log_context['url']

    async def do_check_manifest_url(self, mpd_url: str, mode: str, encrypted: bool,
                              check_head: bool = False) -> ViewsTestDashValidator:
        """
        Test one manifest for validity
        """
        response = None
        # print('check_manifest_url', mpd_url, mode, encrypted)
        response = self.client.get(mpd_url)
        if response.status_code == 302:
            # Handle redirect request
            mpd_url = response.headers['Location']
            self.current_url = mpd_url
            response = self.client.get(mpd_url)
        self.assertIn("Access-Control-Allow-Origin", response.headers)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], '*')
        self.assertEqual(response.headers["Access-Control-Allow-Methods"], "HEAD, GET, POST")
        self.assertEqual(response.status_code, 200)
        xml = ET.parse(io.BytesIO(response.get_data(as_text=False)))
        with ThreadPoolExecutor(max_workers=4) as tpe:
            pool = ConcurrentWorkerPool(tpe)
            dv = ViewsTestDashValidator(
                http_client=self.async_client, mode=mode, pool=pool,
                media_duration=self.MEDIA_DURATION, url=mpd_url,
                encrypted=encrypted)
            await dv.load(xml.getroot())
            await dv.validate()
            if dv.has_errors():
                for err in dv.get_errors():
                    print(err)
        self.assertFalse(dv.has_errors(), 'DASH stream validation failed')
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
            manifest=mpd_filename)
        defaults = OptionsRepository.get_default_options()
        options = OptionsRepository.convert_cgi_options(kwargs, defaults=defaults)
        manifest = manifests.manifest[mpd_filename]
        options.segmentTimeline = manifest.segment_timeline
        options.add_field('mode', mode)
        options.remove_unused_parameters(mode)
        url += options.generate_cgi_parameters_string()
        stream = models.Stream.get(directory=self.FIXTURES_PATH.name)
        self.assertIsNotNone(stream)
        # with self.app.test_request_context(url, method='GET'):
        with self.create_mock_request_context(url, stream):
            context = self.generate_manifest_context(
                mpd_filename, mode=mode, stream=stream, options=options)
            text = flask.render_template(f'manifests/{mpd_filename}', **context)
        encrypted = kwargs.get('drm', 'none') != 'none'
        fixture = self.fixture_filename(mpd_filename, mode, encrypted)
        expected = ET.parse(fixture).getroot()
        actual = ET.fromstring(bytes(text, 'utf-8'))
        self.assertXmlEqual(expected, actual)

    def generate_manifest_context(self, mpd_filename: str, mode: str,
                                  stream: models.Stream, options: OptionsContainer) -> dict:
        mock = MockServeManifest(flask.request)
        context = mock.calculate_manifest_params(mpd_url=mpd_filename, options=options)
        if options.encrypted:
            kids = set()
            for period in context['periods']:
                kids.update(period.key_ids())
            if not kids:
                keys = models.Key.all_as_dict()
            else:
                keys = models.Key.get_kids(kids)
            context["DRM"] = mock.generate_drm_dict(stream, keys, options)
        context['remote_addr'] = mock.request.remote_addr
        context['request_uri'] = mock.request.url
        context['title'] = stream.title
        return context

    @staticmethod
    def fixture_filename(mpd_name, mode, encrypted):
        """returns absolute file path of the given fixture"""
        name, ext = os.path.splitext(mpd_name)
        enc = '_enc' if encrypted else ''
        filename = fr'{name}_{mode}{enc}{ext}'
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
        msg = fr'{msg}: Expected "{expected}" got "{actual}"'
        self.assertEqual(expected, actual, msg=msg)

    def assertXmlEqual(self, expected, actual, index=0, msg=None, strict=False):
        tag = ET.QName(expected.tag)
        if msg is None:
            prefix = tag.localname
        else:
            prefix = fr'{msg}/{tag.localname}'
        if index > 0:
            prefix += fr'[{index:d}]'
        self.assertEqual(
            expected.tag, actual.tag,
            msg=fr'{prefix}: Expected "{expected.tag}" got "{actual.tag}"')
        self.assertXmlTextEqual(
            expected.text, actual.text,
            msg=f'{prefix}: text does not match')
        self.assertXmlTextEqual(
            expected.tail, actual.tail,
            msg=f'{prefix}: tail does not match')

        for name, exp_value in expected.attrib.items():
            key_name = f'{prefix}@{name}'
            self.assertIn(name, actual.attrib, msg=f'Missing attribute {key_name}')
            act_value = actual.attrib[name]
            self.assertEqual(
                exp_value, act_value,
                msg='attribute {} should be "{}" but was "{}"'.format(
                    key_name, exp_value, act_value))
        counts = {}
        for exp, act in zip(expected, actual):
            idx = counts.get(exp.tag, 0)
            self.assertXmlEqual(exp, act, msg=prefix, index=idx)
            counts[exp.tag] = idx + 1
