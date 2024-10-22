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
import os
import logging
from pathlib import Path
from typing import AbstractSet
import urllib.parse

import flask
from lxml import etree as ET

from dashlive.mpeg.dash.profiles import primary_profiles
from dashlive.mpeg.dash.validator import ConcurrentWorkerPool
from dashlive.server import manifests, models
from dashlive.server.options.container import OptionsContainer
from dashlive.server.options.dash_option import DashOption
from dashlive.server.options.utc_time_options import UTCMethod
from dashlive.server.options.repository import OptionsRepository
from dashlive.server.requesthandler.base import TemplateContext
from dashlive.server.requesthandler.manifest_context import ManifestContext
from dashlive.server.requesthandler.manifest_requests import ServeManifest

from .mock_time import MockTime
from .stream_fixtures import StreamFixture, BBB_FIXTURE
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
            self,
            filename: str,
            mode: str,
            simplified: bool = True,
            debug: bool = False,
            now: str | None = None,
            fixture: StreamFixture | None = None,
            **kwargs) -> None:
        """
        Exhaustive test of a manifest with every combination of options
        used by the manifest.
        This test might be _very_ slow (i.e. expect it to take several minutes)
        if the manifest uses lots of features.
        """
        await self.check_a_manifest_using_all_options(
            filename, mode, simplified=simplified, debug=debug, now=now,
            fixture=fixture, **kwargs)

    async def check_a_manifest_using_all_options(
            self,
            filename: str,
            mode: str,
            simplified: bool = False,
            debug: bool = False,
            check_head: bool = False,
            check_media: bool | None = None,
            abr: bool = False,
            with_subs: bool = False,
            only: AbstractSet | None = None,
            extras: list[DashOption] | None = None,
            now: str | None = None,
            duration: int = 0,
            fixture: StreamFixture | None = None,
            **kwargs) -> None:
        """
        Exhaustive test of a manifest with every combination of options
        used by the manifest.
        This test might be _very_ slow (i.e. expect it to take several minutes)
        if the manifest uses lots of features.
        """
        manifest = manifests.manifest_map[filename]
        self.assertIn(mode, primary_profiles)
        modes = manifest.restrictions.get('mode', primary_profiles.keys())
        self.assertIn(mode, modes)
        if fixture is None:
            fixture = BBB_FIXTURE
        self.setup_media_fixture(fixture, with_subs=with_subs)
        self.logout_user()
        self.assertGreaterThan(models.MediaFile.count(), 0)
        test_duration = duration
        if test_duration == 0:
            if mode == 'live':
                test_duration = fixture.segment_duration + fixture.media_duration * 2
            else:
                test_duration = 4 * fixture.segment_duration

        if now is None:
            now = "2024-09-02T09:57:02Z"

        url = flask.url_for(
            'dash-mpd-v3', manifest=filename, mode=mode, stream=fixture.name)

        if not kwargs:
            # do a first pass check with no CGI options
            await self.check_manifest_url(
                url, mode, encrypted=False, debug=debug, duration=test_duration,
                check_media=(check_media in {True, None}), check_head=True, now=now,
                fixture=fixture)

        if check_media is None:
            check_media = not simplified

        utc_method = kwargs.get('utcMethod', '')
        use_base_url = kwargs.get('useBaseUrls', True)
        manifest_kwargs = {
            **kwargs,
            'abr': abr,
            'utcMethod': utc_method,
            'useBaseUrls': use_base_url,
        }
        options = manifest.get_supported_dash_options(
            mode=mode, simplified=simplified, only=only, extras=extras,
            **manifest_kwargs)
        logging.debug('Testing options: %s', options)
        total_tests = options.num_tests
        if 'utcMethod' in manifest.features and 'utcMethod' not in kwargs:
            total_tests += len(UTCMethod.cgi_choices)
        if 'useBaseUrls' in manifest.features and 'useBaseUrls' not in kwargs:
            total_tests += 2

        count = 0
        self.progress(0, total_tests)

        # do an exhaustive check of every option
        for query in options.cgi_query_combinations():
            if 'events=' in query:
                if duration == 0:
                    test_duration = 9 * fixture.segment_duration
                ev_interval = fixture.segment_duration * 300
                if 'ping' in query:
                    query += f'&ping_interval={ev_interval}&ping_timescale=100'
                if 'scte35' in query:
                    query += f'&scte35_interval={ev_interval}&scte35_timescale=100'
            elif duration == 0:
                test_duration = 3 * fixture.segment_duration
            await self.check_manifest_using_options(
                mode, url, query, debug=debug, check_media=check_media,
                now=now, duration=test_duration, check_head=check_head,
                fixture=fixture)
            count += 1
            self.progress(count, total_tests)
        if 'utcMethod' in manifest.features and 'utcMethod' not in kwargs:
            for method in UTCMethod.cgi_choices:
                if method is None or method == utc_method:
                    continue
                query = f'?time={method}'
                await self.check_manifest_using_options(
                    mode, url, query, debug=debug, check_media=False,
                    check_head=False, now=now, duration=test_duration,
                    fixture=fixture)
                count += 1
                self.progress(count, total_tests)
        if 'useBaseUrls' in manifest.features and 'useBaseUrls' not in kwargs:
            for ubu in [True, False]:
                if ubu == use_base_url:
                    continue
                query = f'?base={ubu}'
                await self.check_manifest_using_options(
                    mode, url, query, debug=debug, check_media=False,
                    check_head=False, now=now, duration=test_duration,
                    fixture=fixture)
                count += 1
                self.progress(count, total_tests)
        self.progress(total_tests, total_tests)

    async def check_manifest_using_options(
            self, mode: str, url: str, query: str, debug: bool,
            now: str, duration: int,
            check_media: bool, check_head: bool,
            fixture: StreamFixture) -> None:
        """
        Check one manifest using a specific combination of options.
        :mode: operating mode
        :filename: the filename of the manifest
        :query: the query string
        """
        mpd_url = f'{url}{query}'
        clear = ('drm=none' in query) or ('drm' not in query)
        await self.check_manifest_url(
            mpd_url, mode, encrypted=not clear, debug=debug, check_media=check_media,
            check_head=check_head, now=now, duration=duration, fixture=fixture)

    async def check_manifest_url(
            self, mpd_url: str, mode: str, encrypted: bool, now: str, duration: int,
            debug: bool, check_head: bool, check_media: bool,
            fixture: StreamFixture) -> ViewsTestDashValidator:
        """
        Test one manifest for validity (wrapped in context of MPD url)
        """
        if mpd_url in self.__class__.checked_urls:
            logging.debug('%s already tested', mpd_url)
            return
        try:
            self.log_context.add_item('url', mpd_url)
            self.__class__.checked_urls.add(mpd_url)
            with MockTime(now):
                return await self.do_check_manifest_url(
                    mpd_url, mode, encrypted=encrypted, debug=debug,
                    check_head=check_head, check_media=check_media,
                    duration=duration, fixture=fixture)
        finally:
            del self.log_context['url']

    async def do_check_manifest_url(
            self, mpd_url: str, mode: str, encrypted: bool, debug: bool,
            check_head: bool, check_media: bool, duration: int,
            fixture: StreamFixture) -> ViewsTestDashValidator:
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
            logging.warning('GET %s: %d', mpd_url, response.status_code)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Access-Control-Allow-Origin", response.headers)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], '*')
        self.assertEqual(response.headers["Access-Control-Allow-Methods"], "HEAD, GET, POST")
        timeout: int = 100 if mode == 'live' else 2
        with ThreadPoolExecutor(max_workers=4) as tpe:
            pool = ConcurrentWorkerPool(tpe)
            dv = ViewsTestDashValidator(
                http_client=self.async_client, mode=mode, pool=pool,
                duration=duration, url=mpd_url,
                encrypted=encrypted, debug=debug, check_media=check_media)
            loaded = await dv.load(data=response.get_data(as_text=False))
            if not loaded:
                print(response.get_data(as_text=True))
            while loaded and not dv.finished() and timeout > 0:
                await dv.validate()
                if dv.has_errors():
                    break
                if not dv.finished():
                    timeout -= 1
                    await dv.sleep()
                    logging.info('Refreshing manifest timeout=%d', timeout)
                    await dv.refresh()
        if dv.has_errors():
            dv.print_manifest_text()
            print(f'{mpd_url} has errors:')
            for hist in dv.get_validation_history():
                print(hist)
        self.assertFalse(dv.has_errors(), 'DASH stream validation failed')
        self.assertGreaterThan(
            timeout, 0, 'Timeout waiting for validation to complete')
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
                self.assertAlmostEqual(
                    dur.total_seconds(), fixture.media_duration, delta=1.0)
            else:
                self.assertAlmostEqual(
                    dv.manifest.mediaPresentationDuration.total_seconds(),
                    fixture.media_duration, delta=1.0)
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

    def check_generated_manifest_against_fixture(
            self, mpd_filename: str, mode: str, encrypted: bool,
            now: str, **kwargs) -> None:
        """
        Checks a freshly generated manifest against a "known good"
        previous example
        """
        self.setup_media_fixture(BBB_FIXTURE)
        self.init_xml_namespaces()
        url = flask.url_for(
            "dash-mpd-v3",
            mode=mode,
            stream=BBB_FIXTURE.name,
            manifest=mpd_filename)
        defaults = OptionsRepository.get_default_options()
        options = OptionsRepository.convert_cgi_options(kwargs, defaults=defaults)
        manifest = manifests.manifest_map[mpd_filename]
        options.segmentTimeline = manifest.segment_timeline
        options.add_field('mode', mode)
        options.remove_unused_parameters(mode)
        url += options.generate_cgi_parameters_string()
        stream = models.Stream.get(directory=BBB_FIXTURE.name)
        self.assertIsNotNone(stream)
        with MockTime(now):
            with self.create_mock_request_context(url, stream):
                context = self.generate_manifest_context(
                    mpd_filename, mode=mode, stream=stream, options=options)
                text = flask.render_template(
                    f'manifests/{mpd_filename}', **context)
        fixture = self.fixture_filename(mpd_filename, mode, encrypted)
        if not fixture.exists():
            with fixture.open('wt', encoding='utf-8') as dest:
                dest.write(text)
        expected = ET.parse(str(fixture)).getroot()
        actual = ET.fromstring(bytes(text, 'utf-8'))
        self.assertXmlEqual(expected, actual)

    def generate_manifest_context(
            self,
            mpd_filename: str,
            mode: str,
            stream: models.Stream,
            options: OptionsContainer) -> TemplateContext:
        mock = MockServeManifest(flask.request)
        context: TemplateContext = {
            'mpd': ManifestContext(
                manifest=manifests.manifest_map[mpd_filename],
                options=options,
                multi_period=None,
                stream=stream),
            'mode': mode,
            'options': options,
            'title': stream.title,
            'remote_addr': mock.request.remote_addr,
            'request_uri': mock.request.url,
        }
        return context

    @staticmethod
    def fixture_filename(mpd_name: str, mode: str, encrypted: bool) -> Path:
        """returns absolute file path of the given fixture"""
        name, ext = os.path.splitext(mpd_name)
        enc = '_enc' if encrypted else ''
        filename = f'{name}_{mode}{enc}{ext}'
        return Path(__file__).parent.parent / 'fixtures' / filename

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
                msg='attribute {} expected "{}" found "{}"'.format(
                    key_name, exp_value, act_value))
        counts = {}
        for exp, act in zip(expected, actual):
            idx = counts.get(exp.tag, 0)
            self.assertXmlEqual(exp, act, msg=prefix, index=idx)
            counts[exp.tag] = idx + 1
