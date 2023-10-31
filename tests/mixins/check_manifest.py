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
import json
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
from dashlive.server.options.utc_time_options import UTCMethod
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
    async def check_a_manifest_using_major_options(
            self, filename: str, mode: str, simplified: bool = True,
            debug: bool = False, **kwargs) -> None:
        """
        Exhaustive test of a manifest with every combination of options
        used by the manifest.
        This test might be _very_ slow (i.e. expect it to take several minutes)
        if the manifest uses lots of features.
        """
        await self.check_a_manifest_using_all_options(
            filename, mode, simplified=simplified, debug=debug, **kwargs)

    async def check_a_manifest_using_all_options(
            self,
            filename: str,
            mode: str,
            simplified: bool = False,
            debug: bool = False,
            check_head: bool = False,
            abr: bool = False,
            with_subs: bool = False,
            only: AbstractSet | None = None,
            extras: list[tuple] | None = None,
            **kwargs) -> None:
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
        if mode == 'live':
            duration = self.SEGMENT_DURATION + self.MEDIA_DURATION * 2
        else:
            duration = 4 * self.SEGMENT_DURATION
        # do a first pass check with no CGI options
        url = flask.url_for(
            'dash-mpd-v3',
            manifest=filename,
            mode=mode,
            stream=self.FIXTURES_PATH.name)
        await self.check_manifest_url(
            url, mode, encrypted=False, debug=debug, duration=duration, check_media=True,
            check_head=True)

        utc_method = kwargs.get('utcMethod', '')
        use_base_url = kwargs.get('useBaseUrls', True)
        options = manifest.get_cgi_query_combinations(
            mode=mode, simplified=simplified, only=only, extras=extras,
            abr=abr, utcMethod=utc_method, useBaseUrls=use_base_url, **kwargs)
        total_tests = len(options)
        if 'utcMethod' in manifest.features and 'utcMethod' not in kwargs:
            total_tests += len(UTCMethod.cgi_choices)
        if 'useBaseUrls' in manifest.features and 'useBaseUrls' not in kwargs:
            total_tests += 2
        count = 0
        desc = json.dumps({'mode': mode, **kwargs})
        logging.debug('total %s tests for "%s" = %d', desc, filename, total_tests)
        self.progress(0, total_tests)
        # do an exhaustive check of every option
        for query in options:
            if 'events=' in query:
                duration = 9 * self.SEGMENT_DURATION
                ev_interval = self.SEGMENT_DURATION * 300
                if 'ping' in query:
                    query += f'&ping_interval={ev_interval}&ping_timescale=100'
                if 'scte35' in query:
                    query += f'&scte35_interval={ev_interval}&scte35_timescale=100'
            else:
                duration = 3 * self.SEGMENT_DURATION
            await self.check_manifest_using_options(
                mode, url, query, debug=debug, check_media=True, duration=duration,
                check_head=check_head)
            count += 1
            self.progress(count, total_tests)
        if 'utcMethod' in manifest.features and 'utcMethod' not in kwargs:
            for method in UTCMethod.cgi_choices:
                if method is None or method == utc_method:
                    continue
                query = f'?time={method}'
                await self.check_manifest_using_options(
                    mode, url, query, debug=debug, check_media=False, check_head=False,
                    duration=duration)
                count += 1
                self.progress(count, total_tests)
        if 'useBaseUrls' in manifest.features and 'useBaseUrls' not in kwargs:
            for ubu in [True, False]:
                if ubu == use_base_url:
                    continue
                query = f'?base={ubu}'
                await self.check_manifest_using_options(
                    mode, url, query, debug=debug, check_media=False, check_head=False,
                    duration=duration)
                count += 1
                self.progress(count, total_tests)
        self.progress(total_tests, total_tests)

    async def check_manifest_using_options(
            self, mode: str, url: str, query: str, debug: bool, duration: int,
            check_media: bool, check_head: bool) -> None:
        """
        Check one manifest using a specific combination of options
        :mode: operating mode
        :filename: the filename of the manifest
        :query: the query string
        """
        mpd_url = f'{url}{query}'
        clear = ('drm=none' in query) or ('drm' not in query)
        await self.check_manifest_url(
            mpd_url, mode, encrypted=not clear, debug=debug, check_media=check_media,
            check_head=check_head, duration=duration)

    async def check_manifest_url(
            self, mpd_url: str, mode: str, encrypted: bool, duration: int,
            debug: bool, check_head: bool, check_media: bool) -> ViewsTestDashValidator:
        """
        Test one manifest for validity (wrapped in context of MPD url)
        """
        if mpd_url in self.__class__.checked_urls:
            logging.debug('%s already tested', mpd_url)
            return
        try:
            self.log_context.add_item('url', mpd_url)
            self.__class__.checked_urls.add(mpd_url)
            return await self.do_check_manifest_url(
                mpd_url, mode, encrypted=encrypted, debug=debug, check_head=check_head,
                check_media=check_media, duration=duration)
        finally:
            del self.log_context['url']

    async def do_check_manifest_url(
            self, mpd_url: str, mode: str, encrypted: bool, debug: bool,
            check_head: bool, check_media: bool, duration: int) -> ViewsTestDashValidator:
        """
        Test one manifest for validity
        """
        response = None
        logging.debug('Check manifest (%s, %s): %s', mode, encrypted, mpd_url)
        self.assertIsInstance(mpd_url, str)
        response = self.client.get(mpd_url)
        if response.status_code == 302:
            # Handle redirect request
            mpd_url = response.headers['Location']
            self.current_url = mpd_url
            response = self.client.get(mpd_url)
        if response.status_code != 200:
            print(f'GET {mpd_url}: {response.status_code}')
        self.assertEqual(response.status_code, 200)
        self.assertIn("Access-Control-Allow-Origin", response.headers)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], '*')
        self.assertEqual(response.headers["Access-Control-Allow-Methods"], "HEAD, GET, POST")
        xml = ET.parse(io.BytesIO(response.get_data(as_text=False)))
        with ThreadPoolExecutor(max_workers=4) as tpe:
            pool = ConcurrentWorkerPool(tpe)
            dv = ViewsTestDashValidator(
                http_client=self.async_client, mode=mode, pool=pool,
                duration=duration, url=mpd_url,
                encrypted=encrypted, debug=debug, check_media=check_media)
            await dv.load(xml.getroot())
            await dv.validate()
        if dv.has_errors():
            for idx, line in enumerate(
                    io.StringIO(response.get_data(as_text=True)), start=1):
                print(f'{idx:03d}: {line}')
            print(f'{mpd_url} has errors:')
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
