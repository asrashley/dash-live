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

from __future__ import absolute_import, print_function
import datetime
import io
import os
import logging
import unittest

from lxml import etree
import flask

from dashlive.server import manifests, models
from dashlive.drm.playready import PlayReady
from dashlive.utils.date_time import UTC, toIsoDateTime, from_isodatetime
from dashlive.utils.objects import dict_to_cgi_params

from .flask_base import FlaskTestBase
from .mixins.check_manifest import DashManifestCheckMixin
from .mixins.view_validator import ViewsTestDashValidator

class TestHandlers(FlaskTestBase, DashManifestCheckMixin):
    def test_request_unknown_manifest(self):
        self.setup_media()
        self.logout_user()
        baseurl = flask.url_for(
            'dash-mpd-v3', manifest='unknown.mpd', stream=self.FIXTURES_PATH.name, mode='live')
        resp = self.client.get(baseurl)
        self.assertEqual(resp.status_code, 404)

    def test_request_unknown_mode(self):
        self.setup_media()
        self.logout_user()
        baseurl = flask.url_for(
            'dash-mpd-v3', manifest='hand_made.mpd', stream=self.FIXTURES_PATH.name, mode='unknown')
        resp = self.client.get(baseurl)
        self.assertEqual(resp.status_code, 404)

    def test_request_invalid_num_failures(self):
        self.setup_media()
        self.logout_user()
        baseurl = flask.url_for(
            'dash-mpd-v3', manifest='hand_made.mpd', stream=self.FIXTURES_PATH.name, mode='live')
        url = baseurl + '?failures=foo'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 400)
        url = baseurl + '?m404=foo'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 400)

    def test_legacy_unknown_manifest(self):
        self.setup_media()
        url = flask.url_for('dash-mpd-v1', manifest='unknown.mpd')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_availability_start_time(self):
        """
        Control of MPD@availabilityStartTime using the start parameter
        """
        self.setup_media()
        self.logout_user()
        filename = 'hand_made.mpd'
        manifest = manifests.manifest[filename]
        drm_options = None
        for o in manifest.get_cgi_options():
            if o[0] == 'drm':
                drm_options = o[1]
                break
        self.assertIsNotNone(drm_options)
        self.assertGreaterThan(models.MediaFile.count(), 0)
        ref_now = self.real_datetime_class(2019, 1, 1, 4, 5, 6, tzinfo=UTC())
        ref_today = self.real_datetime_class(2019, 1, 1, tzinfo=UTC())
        ref_yesterday = ref_today - datetime.timedelta(days=1)
        testcases = [
            ('', ref_now, ref_today),
            ('today', ref_now, ref_today),
            ('2019-09-invalid-iso-datetime', ref_now, ref_today),
            ('now', ref_now, ref_now),
            ('epoch', ref_now, datetime.datetime(
                1970, 1, 1, 0, 0, tzinfo=UTC())),
            ('2009-02-27T10:00:00Z', ref_now,
             datetime.datetime(2009, 2, 27, 10, 0, 0, tzinfo=UTC())),
            ('2013-07-25T09:57:31Z', ref_now,
             datetime.datetime(2013, 7, 25, 9, 57, 31, tzinfo=UTC())),
            # special case when "now" is midnight, use yesterday midnight as
            # availabilityStartTime
            ('', ref_today, ref_yesterday),
        ]
        msg = r'When start="%s" is used, expected MPD@availabilityStartTime to be %s but was %s'
        for option, now, start_time in testcases:
            with self.mock_datetime_now(now):
                baseurl = flask.url_for(
                    'dash-mpd-v3',
                    manifest=filename,
                    stream=self.FIXTURES_PATH.name,
                    mode='live')
                if option:
                    baseurl += '?start=' + option
                response = self.client.get(baseurl)
                self.assertEqual(response.status_code, 200)
                xml = etree.parse(io.BytesIO(response.get_data(as_text=False)))
                dv = ViewsTestDashValidator(
                    http_client=self.client, mode='live', xml=xml.getroot(),
                    url=baseurl, encrypted=False, debug=False)
                dv.validate(depth=3)
                if option == 'now':
                    start_time = dv.manifest.publishTime - dv.manifest.timeShiftBufferDepth
                self.assertEqual(dv.manifest.availabilityStartTime, start_time,
                                 msg=msg % (option, start_time.isoformat(),
                                            dv.manifest.availabilityStartTime.isoformat()))
                head = self.client.head(baseurl)
                self.assertEqual(
                    head.headers['Content-Length'],
                    response.headers['Content-Length'])

    def test_create_manifest_error(self):
        self.setup_media()
        self.logout_user()
        start = self.real_datetime_class(2022, 1, 1, 4, 2, 6, tzinfo=UTC())
        before = self.real_datetime_class(2022, 1, 1, 4, 4, 6, tzinfo=UTC())
        active = self.real_datetime_class(2022, 1, 1, 4, 5, 6, tzinfo=UTC())
        after = self.real_datetime_class(2022, 1, 1, 4, 7, 6, tzinfo=UTC())
        baseurl = flask.url_for(
            'dash-mpd-v3',
            manifest='hand_made.mpd',
            stream=self.FIXTURES_PATH.name,
            mode='live')
        for code in [404, 410, 503, 504]:
            params = {
                'm{0:03d}'.format(code): toIsoDateTime(active),
                'start': toIsoDateTime(start),
                'mup': '45',
            }
            url = baseurl + dict_to_cgi_params(params)
            with self.mock_datetime_now(before):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                xml = etree.parse(io.BytesIO(response.get_data(as_text=False)))
                dv = ViewsTestDashValidator(
                    http_client=self.client, mode='live',
                    xml=xml.getroot(), url=url, encrypted=False)
                dv.validate(depth=2)
            with self.mock_datetime_now(active):
                response = self.client.get(url)
                self.assertEqual(
                    response.status_code, code,
                    msg=f'{url}: Expected status code {code} but received {response.status_code}')
            with self.mock_datetime_now(after):
                dv = ViewsTestDashValidator(
                    http_client=self.client, mode='live',
                    url=url, encrypted=False)
                dv.validate(depth=2)

    def test_get_vod_media_using_live_profile(self):
        """Get VoD segments for each DRM type (live profile)"""
        self.setup_media()
        self.logout_user()
        filename = 'hand_made.mpd'
        manifest = manifests.manifest[filename]
        drm_options = None
        for o in manifest.get_cgi_options():
            if o[0] == 'drm':
                drm_options = o[1]
                break
        self.assertIsNotNone(drm_options)
        self.assertGreaterThan(models.MediaFile.count(), 0)
        total_tests = len(drm_options)
        test_count = 0
        for drm_opt in drm_options:
            self.progress(test_count, total_tests)
            test_count += 1
            baseurl = flask.url_for(
                'dash-mpd-v3', manifest=filename, stream=self.FIXTURES_PATH.name, mode='vod')
            baseurl += '?' + drm_opt
            response = self.client.get(baseurl)
            self.assertEqual(response.status_code, 200)
            encrypted = drm_opt != 'drm=none'
            xml = etree.parse(io.BytesIO(response.get_data(as_text=False)))
            mpd = ViewsTestDashValidator(
                http_client=self.client, mode='vod', xml=xml.getroot(),
                url=baseurl, encrypted=encrypted)
            mpd.validate()
            head = self.client.head(baseurl)
            msg = r'Expected HEAD.contentLength={0} == GET.contentLength={1} for URL {2}'.format(
                head.headers['Content-Length'], response.headers['Content-Length'],
                baseurl)
            self.assertEqual(
                head.headers['Content-Length'],
                response.headers['Content-Length'],
                msg)
        self.progress(total_tests, total_tests)

    @FlaskTestBase.mock_datetime_now(from_isodatetime("2022-10-04T12:00:00Z"))
    def test_get_live_media_using_live_profile(self):
        """Get segments from a live stream for each DRM type (live profile)"""
        self.setup_media()
        self.logout_user()
        filename = 'hand_made.mpd'
        manifest = manifests.manifest[filename]
        drm_options = None
        for o in manifest.get_cgi_options():
            if o[0] == 'drm':
                drm_options = o[1]
                break
        self.assertIsNotNone(drm_options)
        self.assertGreaterThan(models.MediaFile.count(), 0)
        total_tests = len(drm_options) * len(PlayReady.MAJOR_VERSIONS)
        test_count = 0
        for drm_opt in drm_options:
            for version in PlayReady.MAJOR_VERSIONS:
                self.progress(test_count, total_tests)
                test_count += 1
                if ('playready' not in drm_opt and
                    'all' not in drm_opt and
                        version != PlayReady.MAJOR_VERSIONS[0]):
                    # when drm_opt is not PlayReady, there is no need to test
                    # each PlayReady version
                    continue
                now = datetime.datetime.now(tz=UTC())
                availabilityStartTime = toIsoDateTime(
                    now - datetime.timedelta(minutes=(1 + (test_count % 20))))
                baseurl = flask.url_for(
                    'dash-mpd-v3', mode='live', manifest=filename, stream=self.FIXTURES_PATH.name)
                options = [
                    drm_opt,
                    'start=' + availabilityStartTime,
                    'playready_version={0}'.format(version)
                ]
                baseurl += '?' + '&'.join(options)
                # 'dash-mpd-v2' will always return a redirect to the v3 URL
                # response = self.client.get(baseurl, status=302)
                # Handle redirect request
                # baseurl = response.headers['Location']
                response = self.client.get(baseurl)
                self.assertEqual(response.status_code, 200)
                encrypted = drm_opt != "drm=none"
                xml = etree.parse(io.BytesIO(response.get_data(as_text=False)))
                mpd = ViewsTestDashValidator(
                    http_client=self.client, mode="live", xml=xml.getroot(),
                    url=baseurl, encrypted=encrypted)
                mpd.validate()
        self.progress(total_tests, total_tests)

    def test_get_vod_media_using_on_demand_profile(self):
        """Get VoD segments (on-demand profile)"""
        self.logout_user()
        self.setup_media()
        for filename, manifest in manifests.manifest.items():
            if 'odvod' not in manifest.supported_modes():
                continue
            baseurl = flask.url_for(
                'dash-mpd-v3',
                mode='odvod',
                manifest=filename,
                stream=self.FIXTURES_PATH.name)
            response = self.client.get(baseurl)
            xml = etree.parse(io.BytesIO(response.get_data(as_text=False)))
            self.assertIn(
                "urn:mpeg:dash:profile:isoff-on-demand:2011",
                xml.getroot().get('profiles'))
            mpd = ViewsTestDashValidator(
                http_client=self.client, mode="odvod", xml=xml.getroot(),
                url=baseurl, encrypted=False)
            mpd.validate()

    def test_request_unknown_media(self):
        url = flask.url_for(
            "dash-media",
            mode="vod",
            stream=self.FIXTURES_PATH.name,
            filename="notfound",
            segment_num=1,
            ext="mp4")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_injected_http_error_codes(self):
        self.setup_media()
        self.logout_user()
        self.assertGreaterThan(models.MediaFile.count(), 0)
        media_files = models.MediaFile.search(max_items=1)
        for seg in range(1, 6):
            url = flask.url_for(
                "dash-media",
                mode="vod",
                stream=self.FIXTURES_PATH.name,
                filename=media_files[0].representation.id,
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
                    f'{code}': '1,3,5',
                    'failures': 2,
                }
                resp = self.client.get(url, query_string=query_string)
                self.assertEqual(resp.status_code, status)

    def test_video_corruption(self):
        self.setup_media()
        self.logout_user()
        self.assertGreaterThan(models.MediaFile.count(content_type='video'), 0)
        video_files = models.MediaFile.search(content_type='video', max_items=1)
        for seg in range(1, 5):
            url = flask.url_for(
                "dash-media",
                mode="vod",
                stream=self.FIXTURES_PATH.name,
                filename=video_files[0].representation.id,
                segment_num=seg,
                ext="m4v")
            clean = self.client.get(url)
            self.assertEqual(clean.status_code, 200)
            corrupt = self.client.get(url, query_string={'corrupt': '1,2'})
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
                stream=self.FIXTURES_PATH.name,
                filename=audio_files[0].representation.id,
                segment_num=seg,
                ext="m4a")
            clean = self.client.get(url)
            self.assertEqual(clean.status_code, 200)
            corrupt = self.client.get(url, query_string={'corrupt': '1,2'})
            self.assertEqual(corrupt.status_code, 200)
            self.assertBuffersEqual(
                clean.get_data(as_text=False),
                corrupt.get_data(as_text=False),
                name=url)


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        logging.basicConfig()
        # logging.getLogger().setLevel(logging.DEBUG)
        # logging.getLogger('mp4').setLevel(logging.INFO)
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            TestHandlers)

if __name__ == '__main__':
    unittest.main()
