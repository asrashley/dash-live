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

from concurrent.futures import ThreadPoolExecutor
import datetime
import io
import logging
import unittest

from lxml import etree
import flask

from dashlive.drm.clearkey import ClearKey
from dashlive.mpeg.dash.validator import ConcurrentWorkerPool
from dashlive.server import manifests, models
from dashlive.server.options.drm_options import DrmLocationOption, PlayreadyVersion
from dashlive.utils.date_time import UTC, to_iso_datetime, from_isodatetime
from dashlive.utils.objects import dict_to_cgi_params, flatten

from .mixins.check_manifest import DashManifestCheckMixin
from .mixins.flask_base import FlaskTestBase
from .mixins.mock_time import MockTime, async_mock_time
from .mixins.view_validator import ViewsTestDashValidator
from .mixins.stream_fixtures import BBB_FIXTURE

class TestHandlers(DashManifestCheckMixin, FlaskTestBase):
    def test_request_unknown_manifest(self):
        self.setup_media_fixture(BBB_FIXTURE)
        self.logout_user()
        baseurl = flask.url_for(
            'dash-mpd-v3', manifest='unknown.mpd',
            stream=BBB_FIXTURE.name, mode='live')
        resp = self.client.get(baseurl)
        self.assertEqual(resp.status_code, 404)

    def test_request_unknown_mode(self):
        self.setup_media_fixture(BBB_FIXTURE)
        self.logout_user()
        baseurl = flask.url_for(
            'dash-mpd-v3', manifest='hand_made.mpd',
            stream=BBB_FIXTURE.name, mode='unknown')
        resp = self.client.get(baseurl)
        self.assertEqual(resp.status_code, 404)

    def test_request_invalid_num_failures(self):
        self.setup_media_fixture(BBB_FIXTURE)
        self.logout_user()
        baseurl = flask.url_for(
            'dash-mpd-v3', manifest='hand_made.mpd',
            stream=BBB_FIXTURE.name, mode='live')
        url = baseurl + '?failures=foo'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 400)
        url = baseurl + '?merr=404=foo'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 400)

    def test_legacy_unknown_manifest(self):
        self.setup_media_fixture(BBB_FIXTURE)
        url = flask.url_for('dash-mpd-v1', manifest='unknown.mpd')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    async def test_availability_start_time(self):
        """
        Control of MPD@availabilityStartTime using the start parameter
        """
        self.setup_media_fixture(BBB_FIXTURE)
        self.logout_user()
        filename = 'hand_made.mpd'
        self.assertGreaterThan(models.MediaFile.count(), 0)
        ref_now = '2019-01-01T04:05:06Z'
        ref_today = '2019-01-01T00:00:00Z'
        ref_yesterday = '2018-12-31T00:00:00Z'
        testcases = [
            ('year', ref_now, ref_today),
            ('month', ref_now, ref_today),
            ('today', ref_now, ref_today),
            ('2019-09-invalid-iso-datetime', ref_now, ref_today),
            ('now', ref_now, ref_now),
            ('epoch', ref_now, '1970-01-01T00:00:00Z'),
            ('2009-02-27T10:00:00Z', ref_now, '2009-02-27T10:00:00Z'),
            ('2013-07-25T09:57:31Z', ref_now, '2013-07-25T09:57:31Z'),
            # special case when "now" is midnight, use yesterday midnight as
            # availabilityStartTime
            ('', ref_today, ref_yesterday),
        ]
        msg = r'When start="{}" is used, expected MPD@availabilityStartTime to be {} but was {}'
        for option, now, start in testcases:
            def mocked_warning(*args):
                self.assertEqual(option, '2019-09-invalid-iso-datetime')

            def mocked_info(*args):
                if 'Invalid CGI parameters' in args[0]:
                    self.assertIn('invalid-iso', option)
                    self.assertIn(option, ' '.join([str(a) for a in args]))
                elif 'availabilityStartTime' in args[0]:
                    self.assertIn('moving availabilityStartTime back one day', args[0])
                    self.assertEqual(now, ref_today)

            with MockTime(now):
                baseurl = flask.url_for(
                    'dash-mpd-v3',
                    manifest=filename,
                    stream=BBB_FIXTURE.name,
                    mode='live')
                if option:
                    baseurl += '?start=' + option
                with unittest.mock.patch.object(logging, 'warning', mocked_warning):
                    with unittest.mock.patch.object(logging, 'info', mocked_info):
                        response = self.client.get(baseurl)
                if 'invalid-iso' in option:
                    self.assertEqual(response.status_code, 400)
                    continue
                self.assertEqual(response.status_code, 200,
                                 msg=f'Failed to fetch manifest {baseurl}')
                with ThreadPoolExecutor(max_workers=4) as tpe:
                    pool = ConcurrentWorkerPool(tpe)
                    dv = ViewsTestDashValidator(
                        http_client=self.async_client, mode='live', pool=pool,
                        url=baseurl, encrypted=False, debug=False, check_media=False,
                        duration=int(BBB_FIXTURE.media_duration // 3))
                    await dv.load(data=response.get_data(as_text=False))
                    await dv.validate()
                if dv.has_errors():
                    dv.print_manifest_text()
                self.assertFalse(dv.has_errors(), 'Validation failed')
                today = from_isodatetime(now).replace(
                    hour=0, minute=0, second=0, microsecond=0)
                start_time = from_isodatetime(start)
                if option != 'today' and today == start_time:
                    start_time -= datetime.timedelta(days=1)
                elif option == 'now':
                    start_time = from_isodatetime(now) - dv.manifest.timeShiftBufferDepth
                self.assertEqual(
                    dv.manifest.availabilityStartTime,
                    start_time,
                    msg=msg.format(
                        option, start_time.isoformat(),
                        dv.manifest.availabilityStartTime.isoformat()))
                with unittest.mock.patch.object(logging, 'warning', mocked_warning):
                    with unittest.mock.patch.object(logging, 'info', mocked_info):
                        head = self.client.head(baseurl)
                self.assertEqual(
                    head.headers['Content-Length'],
                    response.headers['Content-Length'])

    async def test_create_manifest_error(self):
        self.setup_media_fixture(BBB_FIXTURE)
        self.logout_user()
        start = '2022-01-01T04:02:06Z'
        before = '2022-01-01T04:04:06Z'
        active = '2022-01-01T04:05:06Z'
        after = '2022-01-01T04:07:06Z'
        baseurl = flask.url_for(
            'dash-mpd-v3',
            manifest='hand_made.mpd',
            stream=BBB_FIXTURE.name,
            mode='live')
        for code in [404, 410, 503, 504]:
            params = {
                'merr': f'{code:3d}={active}',
                'start': start,
                'mup': '45',
            }
            url = baseurl + dict_to_cgi_params(params)
            with MockTime(before):
                with ThreadPoolExecutor(max_workers=4) as tpe:
                    pool = ConcurrentWorkerPool(tpe)
                    dv = ViewsTestDashValidator(
                        http_client=self.async_client, mode='live', pool=pool, check_media=False,
                        url=url, encrypted=False,
                        duration=int(BBB_FIXTURE.media_duration * 1.5))
                    self.assertTrue(await dv.load())
                    await dv.validate()
                self.assertFalse(dv.has_errors(), msg='stream validation failed')
            with MockTime(active):
                response = self.client.get(url)
                self.assertEqual(
                    response.status_code, code,
                    msg=f'{url}: Expected status code {code} but received {response.status_code}')
            with MockTime(after):
                with ThreadPoolExecutor(max_workers=4) as tpe:
                    pool = ConcurrentWorkerPool(tpe)
                    dv = ViewsTestDashValidator(
                        http_client=self.async_client, mode='live', pool=pool, check_media=False,
                        url=url, encrypted=False,
                        duration=(2 * BBB_FIXTURE.segment_duration))
                    await dv.validate()
                    self.assertFalse(dv.has_errors())

    @async_mock_time("2000-10-07T07:56:58Z")
    async def test_get_vod_media_using_live_profile(self):
        """Get VoD segments for each DRM type (live profile)"""
        self.setup_media_fixture(BBB_FIXTURE)
        self.logout_user()
        filename = 'hand_made.mpd'
        manifest = manifests.manifest_map[filename]
        drm_options = manifest.get_supported_dash_options('vod', only={'drmSelection'})
        self.assertGreaterThan(drm_options.num_tests, 0)
        self.assertGreaterThan(models.MediaFile.count(), 0)
        test_count = 0
        baseurl = flask.url_for(
            'dash-mpd-v3', manifest=filename, stream=BBB_FIXTURE.name, mode='vod')
        for drm_opt in drm_options.cgi_query_combinations():
            self.progress(test_count, drm_options.num_tests)
            test_count += 1
            mpd_url = baseurl + drm_opt
            # print('test_get_vod_media_using_live_profile', mpd_url)
            response = self.client.get(mpd_url)
            self.assertEqual(response.status_code, 200)
            encrypted = ('drm=none' not in drm_opt) and ('drm=' in drm_opt)
            xml = etree.parse(io.BytesIO(response.get_data(as_text=False)))
            with ThreadPoolExecutor(max_workers=4) as tpe:
                pool = ConcurrentWorkerPool(tpe)
                mpd = ViewsTestDashValidator(
                    http_client=self.async_client, mode='vod', check_media=True,
                    url=mpd_url, encrypted=encrypted, pool=pool,
                    duration=int(BBB_FIXTURE.media_duration // 2))
                await mpd.load(xml.getroot())
                await mpd.validate()
            if mpd.has_errors():
                print(mpd_url)
                mpd.print_manifest_text()
                for err in mpd.get_errors():
                    print(err)
            self.assertFalse(mpd.has_errors(), 'DASH validation failed')
            head = self.client.head(mpd_url)
            msg = r'Expected HEAD.contentLength={} == GET.contentLength={} for URL {}'.format(
                head.headers['Content-Length'], response.headers['Content-Length'],
                baseurl)
            self.assertEqual(
                head.headers['Content-Length'],
                response.headers['Content-Length'],
                msg)
        self.progress(drm_options.num_tests, drm_options.num_tests)

    @async_mock_time("2022-10-04T12:00:00Z")
    async def test_get_live_media_using_live_profile(self) -> None:
        """Get segments from a live stream for each DRM type (live profile)"""
        self.setup_media_fixture(BBB_FIXTURE)
        self.logout_user()
        filename = 'hand_made.mpd'
        drm_options = ['drm=all', 'drm=marlin']
        # add all combinations of PlayReady options
        for choice in DrmLocationOption.cgi_choices:
            if choice[1] is None:
                drm_options.append('drm=playready')
                continue
            for version in PlayreadyVersion.cgi_choices:
                if version is None:
                    continue
                # Playready version 1.0 only allows mspr:pro element
                if float(version) < 2.0 and choice[1] != 'pro':
                    continue
                drm_options.append(f'drm=playready-{choice[1]}&playready_version={version}')
        for choice in DrmLocationOption.cgi_choices:
            if choice[1] is None:
                drm_options.append('drm=clearkey')
                continue
            if 'pro' in choice[1]:
                continue
            drm_options.append(f'drm=clearkey-{choice[1]}')
        self.assertGreaterThan(models.MediaFile.count(), 0)
        total_tests = len(drm_options)
        test_count = 0
        # logging.getLogger('wsgi').setLevel(logging.DEBUG)
        for drm_opt in drm_options:
            self.progress(test_count, total_tests)
            test_count += 1
            now = datetime.datetime.now(tz=UTC())
            availabilityStartTime = to_iso_datetime(
                now - datetime.timedelta(minutes=(1 + (test_count % 20))))
            baseurl = flask.url_for(
                'dash-mpd-v3', mode='live', manifest=filename,
                stream=BBB_FIXTURE.name)
            options = [
                drm_opt,
                'abr=0',
                'start=' + availabilityStartTime
            ]
            baseurl += '?' + '&'.join(options)
            encrypted = drm_opt != "drm=none"
            with ThreadPoolExecutor(max_workers=4) as tpe:
                pool = ConcurrentWorkerPool(tpe)
                mpd = ViewsTestDashValidator(
                    http_client=self.async_client, mode="live", pool=pool,
                    debug=False, url=baseurl, encrypted=encrypted,
                    duration=(2 * BBB_FIXTURE.media_duration))
                self.assertTrue(await mpd.load())
                await mpd.validate()
            if mpd.has_errors():
                print(baseurl)
                for err in mpd.get_errors():
                    print(err)
            self.assertFalse(mpd.has_errors(), msg='Stream validation failed')
        self.progress(total_tests, total_tests)

    async def test_get_vod_media_using_on_demand_profile(self):
        """Get VoD segments (on-demand profile)"""
        self.logout_user()
        self.setup_media_fixture(BBB_FIXTURE)
        for filename, manifest in manifests.manifest_map.items():
            if 'odvod' not in manifest.supported_modes():
                continue
            baseurl = flask.url_for(
                'dash-mpd-v3',
                mode='odvod',
                manifest=filename,
                stream=BBB_FIXTURE.name)
            response = self.client.get(baseurl)
            xml = etree.parse(io.BytesIO(response.get_data(as_text=False)))
            self.assertIn(
                "urn:mpeg:dash:profile:isoff-on-demand:2011",
                xml.getroot().get('profiles'))
            with ThreadPoolExecutor(max_workers=4) as tpe:
                pool = ConcurrentWorkerPool(tpe)
                mpd = ViewsTestDashValidator(
                    http_client=self.async_client, mode="odvod", url=baseurl,
                    encrypted=False, pool=pool,
                    duration=int(BBB_FIXTURE.media_duration // 2))
                await mpd.load(xml.getroot())
                await mpd.validate()
            if mpd.has_errors():
                manifest_text: list[str] = []
                for line in io.StringIO(response.get_data(as_text=True)):
                    manifest_text.append(line[:-1])
                for idx, txt in enumerate(manifest_text, start=1):
                    print(f'{idx:#03d}: {txt}')
                for err in mpd.get_errors():
                    print(err)
            self.assertFalse(mpd.has_errors(), msg='Stream validation failed')

    def test_request_unknown_media(self):
        url = flask.url_for(
            "dash-media",
            mode="vod",
            stream=BBB_FIXTURE.name,
            filename="notfound",
            segment_num=1,
            ext="mp4")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_injected_http_error_codes(self):
        self.setup_media_fixture(BBB_FIXTURE, with_subs=True)
        self.logout_user()
        self.assertGreaterThan(models.MediaFile.count(), 0)
        media_files = [
            models.MediaFile.search(max_items=1, content_type='video')[0],
            models.MediaFile.search(max_items=1, content_type='audio')[0],
            models.MediaFile.search(max_items=1, content_type='text')[0],
        ]
        for mf in media_files:
            if mf.content_type == 'video':
                param = 'verr'
            elif mf.content_type == 'audio':
                param = 'aerr'
            else:
                param = 'terr'
            for seg in range(1, 6):
                if mf.content_type == 'text' and seg > 2:
                    # text file fixture has only 2 segments
                    continue
                url = flask.url_for(
                    "dash-media",
                    mode="vod",
                    stream=BBB_FIXTURE.name,
                    filename=mf.representation.id,
                    segment_num=seg,
                    ext="mp4")
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                for code in [404, 410, 503, 504]:
                    # 5xx errors are only returned "failures" number of times.
                    # This means that the request for segment 5 will succeed
                    if code < 500 and seg in {1, 3, 5}:
                        status = code
                    elif code >= 500 and seg in {1, 3}:
                        status = code
                    else:
                        status = 200
                    query_string = {
                        param: f'{code}=1,{code}=3,{code}=5',
                        'failures': 2,
                    }
                resp = self.client.get(url, query_string=query_string)
                self.assertEqual(
                    resp.status_code, status,
                    msg=f'{url}: Expected HTTP status {status} but found {resp.status_code}')

    def test_video_corruption(self):
        self.setup_media_fixture(BBB_FIXTURE)
        self.logout_user()
        self.assertGreaterThan(models.MediaFile.count(content_type='video'), 0)
        video_files = models.MediaFile.search(content_type='video', max_items=1)
        for seg in range(1, 5):
            url = flask.url_for(
                "dash-media",
                mode="vod",
                stream=BBB_FIXTURE.name,
                filename=video_files[0].representation.id,
                segment_num=seg,
                ext="m4v")
            clean = self.client.get(url)
            self.assertEqual(clean.status_code, 200)
            corrupt = self.client.get(url, query_string={'vcorrupt': '1,2'})
            self.assertEqual(corrupt.status_code, 200)
            if seg < 3:
                self.assertBuffersNotEqual(
                    clean.get_data(as_text=False),
                    corrupt.get_data(as_text=False),
                    name=url)
            else:
                self.assertBuffersEqual(
                    clean.get_data(as_text=False),
                    corrupt.get_data(as_text=False),
                    name=url)
        self.assertGreaterThan(models.MediaFile.count(content_type='audio'), 0)
        audio_files = models.MediaFile.search(content_type='audio', max_items=1)
        for seg in range(1, 5):
            url = flask.url_for(
                "dash-media",
                mode="vod",
                stream=BBB_FIXTURE.name,
                filename=audio_files[0].representation.id,
                segment_num=seg,
                ext="m4a")
            clean = self.client.get(url)
            self.assertEqual(clean.status_code, 200)
            corrupt = self.client.get(url, query_string={'vcorrupt': '1,2'})
            self.assertEqual(corrupt.status_code, 200)
            self.assertBuffersEqual(
                clean.get_data(as_text=False),
                corrupt.get_data(as_text=False),
                name=url)

    async def test_get_vod_media_with_stream_defaults(self):
        """
        Get VoD segments where the stream has defaults
        """
        self.setup_media_fixture(BBB_FIXTURE)
        with self.app.app_context():
            bbb = models.Stream.get(directory=BBB_FIXTURE.name)
            assert bbb is not None
            bbb.defaults = flatten({
                'abr': '0',
                'availabilityStartTime': 'epoch',
                'ping': {
                    'count': 5
                },
                'timeShiftBufferDepth': 120,
                'eventTypes': ['ping'],
                'drmSelection': [
                    ('clearkey', {'cenc'})
                ]
            })
            models.db.session.commit()
        self.logout_user()
        mpd_url = flask.url_for(
            'dash-mpd-v3', manifest='hand_made.mpd', stream=BBB_FIXTURE.name,
            mode='vod')
        with ThreadPoolExecutor(max_workers=4) as tpe:
            pool = ConcurrentWorkerPool(tpe)
            mpd = ViewsTestDashValidator(
                http_client=self.async_client, mode='vod', url=mpd_url, encrypted=True,
                pool=pool, check_media=True,
                duration=int(BBB_FIXTURE.media_duration // 2))
            self.assertTrue(await mpd.load())
            await mpd.validate()
        if mpd.has_errors():
            print(mpd_url)
            for err in mpd.get_errors():
                print(err)
        self.assertFalse(mpd.has_errors(), 'Stream validation failed')
        for adp in mpd.manifest.periods[0].adaptation_sets:
            if adp.contentType != 'video':
                continue
            self.assertEqual(len(adp.event_streams), 1)
            self.assertEqual(adp.event_streams[0].schemeIdUri, r'urn:dash-live:pingpong:2022')
            schemes = {cp.schemeIdUri for cp in adp.contentProtection}
            self.assertIn(f"urn:uuid:{ClearKey.MPD_SYSTEM_ID}", schemes)


if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    unittest.main()
