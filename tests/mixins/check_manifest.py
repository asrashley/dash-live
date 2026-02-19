#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import datetime
from functools import wraps
import math
import os
import logging
from pathlib import Path
from typing import AbstractSet, ClassVar
import urllib.parse

import flask
from lxml import etree as ET

from dashlive.mpeg.dash.profiles import primary_profiles
from dashlive.mpeg.dash.validator import ConcurrentWorkerPool
from dashlive.mpeg.dash.validator.errors import ValidationError
from dashlive.server import manifests, models
from dashlive.server.options.container import OptionsContainer
from dashlive.server.options.types import OptionUsage
from dashlive.server.requesthandler.base import TemplateContext
from dashlive.server.requesthandler.manifest_context import ManifestContext
from dashlive.server.requesthandler.manifest_requests import ServeManifest

from .mock_time import MockTime
from .stream_fixtures import MPS_FIXTURE, StreamFixture, BBB_FIXTURE
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
    progress: Callable[[int, int], None]
    checked_urls: ClassVar[set[str]]

    async def check_a_manifest_using_major_options(
            self,
            filename: str,
            mode: str,
            mps_name: str | None = None,
            simplified: bool = True,
            debug: bool = False,
            now: str | None = None,
            fixture: StreamFixture | None = None,
            check_media: bool | None = None,
            **kwargs) -> None:
        """
        Exhaustive test of a manifest with all combinations of commonly used options.
        """
        await self.check_a_manifest_using_all_options(
            filename, mode, simplified=simplified, debug=debug, now=now,
            mps_name=mps_name, fixture=fixture, check_media=check_media, **kwargs)

    async def check_a_manifest_using_all_options(
            self,
            filename: str,
            mode: str,
            mps_name: str | None = None,
            simplified: bool = False,
            debug: bool = False,
            check_head: bool = False,
            check_media: bool | None = None,
            abr: bool = False,
            with_subs: bool = False,
            only: AbstractSet | None = None,
            extras: list[manifests.SupportedOptionTuple] | None = None,
            now: str | None = None,
            duration: float = 0,
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
            if mps_name:
                fixture = MPS_FIXTURE
                self.setup_multi_period_stream(MPS_FIXTURE)
            else:
                fixture = BBB_FIXTURE
                self.setup_media_fixture(fixture, with_subs=with_subs)
        self.logout_user()
        self.assertGreaterThan(models.MediaFile.count(), 0)
        mps: models.MultiPeriodStream | None = None
        if mps_name is not None:
            mps = models.MultiPeriodStream.get(name=mps_name)
            assert mps is not None
        test_duration: float = duration
        if test_duration < 1:
            if mode == 'live':
                if mps is not None:
                    test_duration = mps.total_duration().total_seconds() * 2
                else:
                    test_duration = fixture.segment_duration + fixture.media_duration * 2
            else:
                if mps is not None:
                    test_duration = mps.total_duration().total_seconds()
                else:
                    test_duration = 4 * fixture.segment_duration

        if now is None:
            now = "2024-09-02T09:57:02Z"

        url: str
        if mps_name is not None:
            url = flask.url_for(
                'mps-manifest', manifest=filename, mode=mode, mps_name=mps_name)
        else:
            url = flask.url_for(
                'dash-mpd-v3', manifest=filename, mode=mode, stream=fixture.name)

        if debug:
            wsgi_log = logging.getLogger('wsgi')
            wsgi_log.setLevel(logging.DEBUG)
        if not kwargs:
            # do a first pass check with no CGI options
            await self.check_manifest_url(
                url, mode, encrypted=False, debug=debug, duration=test_duration,
                check_media=(check_media in {True, None}), check_head=True, now=now,
                fixture=fixture)

        if check_media is None:
            check_media = not simplified

        use_base_url = kwargs.get('useBaseUrls', True)
        manifest_kwargs = {
            **kwargs,
            'abr': abr,
            'useBaseUrls': use_base_url,
        }
        options: manifests.SupportedOptionTupleList = manifest.get_supported_dash_options(
            mode=mode, simplified=simplified, only=only, extras=extras, use=OptionUsage.MANIFEST,
            **manifest_kwargs)
        logging.debug('Testing options: %s', options)
        total_tests: int = options.num_tests
        if 'useBaseUrls' in manifest.features and 'useBaseUrls' not in kwargs:
            total_tests += 2

        count = 0
        self.progress(0, total_tests)

        # do an exhaustive check of every option
        for query in options.cgi_query_combinations():
            if 'events=' in query:
                if duration == 0:
                    test_duration = int(math.ceil(9 * fixture.segment_duration))
                ev_interval = fixture.segment_duration * 300
                if 'ping' in query:
                    query += f'&ping_interval={ev_interval}&ping_timescale=100'
                if 'scte35' in query:
                    query += f'&scte35_interval={ev_interval}&scte35_timescale=100'
            elif duration == 0:
                test_duration = int(math.ceil(3 * fixture.segment_duration))
            with self.subTest(query=query, test_duration=test_duration):
                await self.check_manifest_using_options(
                    mode, url, query, debug=debug, check_media=check_media,
                    now=now, duration=test_duration, check_head=check_head,
                    fixture=fixture)
            count += 1
            self.progress(count, total_tests)
        if 'useBaseUrls' in manifest.features and 'useBaseUrls' not in kwargs:
            query = f'?base={not use_base_url}'
            with self.subTest(query=query):
                await self.check_manifest_using_options(
                    mode, url, query, debug=debug, check_media=False, check_head=False,
                    now=now, duration=test_duration, fixture=fixture)
            count += 1
            self.progress(count, total_tests)
        self.progress(total_tests, total_tests)

    async def check_manifest_using_options(
            self, mode: str, url: str, query: str, debug: bool,
            now: str, duration: float,
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
            self, mpd_url: str, mode: str, encrypted: bool, now: str, duration: float,
            debug: bool, check_head: bool, check_media: bool,
            fixture: StreamFixture) -> ViewsTestDashValidator | None:
        """
        Test one manifest for validity (wrapped in context of MPD url)
        """
        if mpd_url in self.__class__.checked_urls:
            logging.debug('%s already tested', mpd_url)
            return
        try:
            self.log_context.add_item('url', mpd_url)
            self.__class__.checked_urls.add(mpd_url)
            logging.debug("Using mocked time %s", now)
            with MockTime(now):
                return await self.do_check_manifest_url(
                    mpd_url, mode, encrypted=encrypted, debug=debug,
                    check_head=check_head, check_media=check_media,
                    duration=duration, fixture=fixture)
        finally:
            del self.log_context['url']

    async def do_check_manifest_url(
            self, mpd_url: str, mode: str, encrypted: bool, debug: bool,
            check_head: bool, check_media: bool, duration: float,
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
        allowed_methods: set[str] = {
            m.strip() for m in response.headers["Access-Control-Allow-Methods"].split(",")
        }
        self.assertEqual(allowed_methods, {"HEAD", "GET"})
        timeout: int = 100 if mode == 'live' else 2
        with ThreadPoolExecutor(max_workers=4) as tpe:
            pool = ConcurrentWorkerPool(tpe)
            dv = ViewsTestDashValidator(
                http_client=self.async_client, mode=mode, pool=pool,
                duration=int(math.ceil(duration)), url=mpd_url,
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
            errs: list[ValidationError] = dv.get_errors()
            print(f'{mpd_url} has {len(errs)} validation errors:')
            for idx, hist in enumerate(errs):
                print(f"{idx:03d}: {hist}")
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
                msg: str = (
                    f"{fixture.name}: Expected media duration {fixture.media_duration} " +
                    f"found {dv.manifest.mediaPresentationDuration.total_seconds()}")
                self.assertAlmostEqual(
                    dv.manifest.mediaPresentationDuration.total_seconds(),
                    fixture.media_duration, delta=1.0, msg=msg)
        return dv

    @contextmanager
    def create_mock_request_context(self,
                                    url: str,
                                    stream: models.Stream | None,
                                    mps_stream: models.MultiPeriodStream | None,
                                    method: str = 'GET'):
        abs_url: str = urllib.parse.urljoin('http://unit.test/', url)
        parsed = urllib.parse.urlparse(abs_url)
        with self.app.test_request_context(url, method='GET') as context:
            flask.g.stream = stream
            flask.g.mp_stream = mps_stream
            context.request.url = abs_url
            context.request.scheme = parsed.scheme
            context.request.remote_addr = '127.0.0.1'
            context.request.host = r'unit.test'
            context.request.host_url = r'http://unit.test/'
            yield context

    def check_generated_manifest_against_fixture(
            self,
            mpd_filename: str,
            mode: str,
            encrypted: bool,
            now: str,
            mps_name: str | None = None,
            **kwargs) -> None:
        """
        Checks a freshly generated manifest against a "known good"
        previous example
        """
        self.setup_media_fixture(BBB_FIXTURE)
        self.init_xml_namespaces()
        if mps_name is not None:
            url: str = flask.url_for(
                "mps-manifest",
                mode=mode,
                mps_name=mps_name,
                manifest=mpd_filename)
        else:
            url = flask.url_for(
                "dash-mpd-v3",
                mode=mode,
                stream=BBB_FIXTURE.name,
                manifest=mpd_filename)
        options = OptionsContainer(mode=mode)
        options.apply_options(params=kwargs, is_cgi=True)
        manifest = manifests.manifest_map[mpd_filename]
        options.segmentTimeline = manifest.segment_timeline
        options.reset_unused_parameters(mode=mode, encrypted=encrypted)
        url += options.generate_cgi_parameters_string()
        stream: models.Stream | None = None
        mps: models.MultiPeriodStream | None = None
        if mps_name is not None:
            mps = models.MultiPeriodStream.get(name=mps_name)
            assert mps is not None
        else:
            stream = models.Stream.get(directory=BBB_FIXTURE.name)
            assert stream is not None
        text: str = ""
        with MockTime(now):
            with self.create_mock_request_context(url, stream, mps):
                context = self.generate_manifest_context(
                    mpd_filename, mode=mode, stream=stream,
                    mps=mps, options=options)
                text = flask.render_template(
                    f'manifests/{mpd_filename}', **context)
        fixture, real_fixture = self.fixture_filename(
            mpd_filename, mode, encrypted, mps_name is not None)
        # reading XML from a file using ElementTree does not work with
        # pyfakefs, so disable it when loading or creating the fixture
        self.fs.pause()
        if not real_fixture.exists():
            print(f"Creating MPD fixture file: {real_fixture}")
            with real_fixture.open('wt', encoding='utf-8') as dest:
                dest.write(text)
        expected = ET.parse(str(real_fixture)).getroot()
        self.fs.resume()
        actual = ET.fromstring(bytes(text, 'utf-8'))
        self.assertXmlEqual(expected, actual)

    def generate_manifest_context(
            self,
            mpd_filename: str,
            mode: str,
            stream: models.Stream | None,
            mps: models.MultiPeriodStream | None,
            options: OptionsContainer) -> TemplateContext:
        mock = MockServeManifest(flask.request)
        context: TemplateContext = {
            'mpd': ManifestContext(
                manifest=manifests.manifest_map[mpd_filename],
                options=options,
                multi_period=mps,
                stream=stream),
            'mode': mode,
            'options': options,
            'title': mps.title if mps is not None else stream.title,
            'remote_addr': mock.request.remote_addr,
            'request_uri': mock.request.url,
        }
        return context

    def fixture_filename(self, mpd_name: str, mode: str, encrypted: bool,
                         multi_period: bool = False) -> tuple[Path, Path]:
        """returns absolute file path of the given fixture"""
        name, ext = os.path.splitext(mpd_name)
        enc: str = '_enc' if encrypted else ''
        mps: str = 'mps_' if multi_period else ''
        filename = f'{name}_{mps}{mode}{enc}{ext}'
        return [self.fixtures_folder / filename, self.REAL_FIXTURES_PATH / filename]

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

    def assertXmlTextEqual(self, expected, actual, msg: str | None = None) -> None:
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

    def assertXmlEqual(self,
                       expected: ET.Element,
                       actual: ET.Element,
                       index: int = 0,
                       msg: str | None = None,
                       strict: bool = False) -> None:
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
