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

from __future__ import print_function
import base64
import datetime
import os
import unittest
try:
    from unittest import mock
except ImportError:
    # use Python 2 back-port
    import mock
import urllib
import sys

_src = os.path.join(os.path.dirname(__file__), "..", "src")
if _src not in sys.path:
    sys.path.append(_src)

# these imports *must* be after the modification of sys.path
from mixins.manifest import DashManifestCheckMixin
import manifests
import utils
import models
from drm.playready import PlayReady
from gae_base import GAETestBase
from view_validator import ViewsTestDashValidator

real_datetime_class = datetime.datetime

def mock_datetime_now(target):
    """Override ``datetime.datetime.now()`` with a custom target value.
    This creates a new datetime.datetime class, and alters its now()/utcnow()
    methods.
    Returns:
        A mock.patch context, can be used as a decorator or in a with.
    """
    # See http://bugs.python.org/msg68532
    # And
    # http://docs.python.org/reference/datamodel.html#customizing-instance-and-subclass-checks
    class DatetimeSubclassMeta(type):
        """We need to customize the __instancecheck__ method for isinstance().
        This must be performed at a metaclass level.
        """
        @classmethod
        def __instancecheck__(mcs, obj):
            return isinstance(obj, real_datetime_class)

    class BaseMockedDatetime(real_datetime_class):
        @classmethod
        def now(cls, tz=None):
            return target.replace(tzinfo=tz)

        @classmethod
        def utcnow(cls):
            return target

    # Python2 & Python3-compatible metaclass
    MockedDatetime = DatetimeSubclassMeta(
        'datetime', (BaseMockedDatetime,), {})
    return mock.patch.object(datetime, 'datetime', MockedDatetime)


class TestHandlers(GAETestBase, DashManifestCheckMixin):
    def test_availability_start_time(self):
        """Control of MPD@availabilityStartTime using the start parameter"""
        self.setup_media()
        self.logoutCurrentUser()
        filename = 'hand_made.mpd'
        manifest = manifests.manifest[filename]
        drm_options = None
        for o in manifest.get_cgi_options():
            if o[0] == 'drm':
                drm_options = o[1]
                break
        self.assertIsNotNone(drm_options)
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        ref_now = real_datetime_class(2019, 1, 1, 4, 5, 6, tzinfo=utils.UTC())
        ref_today = real_datetime_class(2019, 1, 1, tzinfo=utils.UTC())
        ref_yesterday = ref_today - datetime.timedelta(days=1)
        testcases = [
            ('', ref_now, ref_today),
            ('today', ref_now, ref_today),
            ('2019-09-invalid-iso-datetime', ref_now, ref_today),
            ('now', ref_now, ref_now),
            ('epoch', ref_now, datetime.datetime(
                1970, 1, 1, 0, 0, tzinfo=utils.UTC())),
            ('2009-02-27T10:00:00Z', ref_now,
             datetime.datetime(2009, 2, 27, 10, 0, 0, tzinfo=utils.UTC())),
            ('2013-07-25T09:57:31Z', ref_now,
             datetime.datetime(2013, 7, 25, 9, 57, 31, tzinfo=utils.UTC())),
            # special case when "now" is midnight, use yesterday midnight as
            # availabilityStartTime
            ('', ref_today, ref_yesterday),
        ]
        msg = r'When start="%s" is used, expected MPD@availabilityStartTime to be %s but was %s'
        for option, now, start_time in testcases:
            with mock_datetime_now(now):
                baseurl = self.from_uri(
                    'dash-mpd-v3',
                    manifest=filename,
                    stream='bbb',
                    mode='live')
                if option:
                    baseurl += '?start=' + option
                response = self.app.get(baseurl)
                dv = ViewsTestDashValidator(
                    self.app, 'live', response.xml, baseurl)
                dv.validate(depth=3)
                if option == 'now':
                    start_time = dv.manifest.publishTime - dv.manifest.timeShiftBufferDepth
                self.assertEqual(dv.manifest.availabilityStartTime, start_time,
                                 msg=msg % (option, start_time.isoformat(),
                                            dv.manifest.availabilityStartTime.isoformat()))

    def test_get_vod_media_using_live_profile(self):
        """Get VoD segments for each DRM type (live profile)"""
        self.setup_media()
        self.logoutCurrentUser()
        filename = 'hand_made.mpd'
        manifest = manifests.manifest[filename]
        drm_options = None
        for o in manifest.get_cgi_options():
            if o[0] == 'drm':
                drm_options = o[1]
                break
        self.assertIsNotNone(drm_options)
        # pr = drm.PlayReady(self.templates)
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        total_tests = len(drm_options)
        test_count = 0
        for drm_opt in drm_options:
            self.progress(test_count, total_tests)
            test_count += 1
            baseurl = self.from_uri(
                'dash-mpd-v2', manifest=filename, stream='bbb')
            baseurl += '?mode=vod&' + drm_opt
            response = self.app.get(baseurl)
            mpd = ViewsTestDashValidator(
                self.app, 'vod', response.xml, baseurl)
            mpd.validate()
        self.progress(total_tests, total_tests)

    def test_get_live_media_using_live_profile(self):
        """Get segments from a live stream for each DRM type (live profile)"""
        self.setup_media()
        self.logoutCurrentUser()
        filename = 'hand_made.mpd'
        manifest = manifests.manifest[filename]
        drm_options = None
        for o in manifest.get_cgi_options():
            if o[0] == 'drm':
                drm_options = o[1]
                break
        self.assertIsNotNone(drm_options)
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
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
                now = datetime.datetime.now(tz=utils.UTC())
                availabilityStartTime = utils.toIsoDateTime(
                    now - datetime.timedelta(minutes=(1 + (test_count % 20))))
                baseurl = self.from_uri(
                    'dash-mpd-v2', manifest=filename, stream='bbb')
                options = [
                    'mode=live', drm_opt, 'start=' + availabilityStartTime,
                    'playready_version={0}'.format(version)
                ]
                baseurl += '?' + '&'.join(options)
                response = self.app.get(baseurl)
                self.assertEqual(response.status_int, 200)
                mpd = ViewsTestDashValidator(
                    self.app, "live", response.xml, baseurl)
                mpd.validate()
        self.progress(total_tests, total_tests)

    def test_get_vod_media_using_on_demand_profile(self):
        """Get VoD segments (on-demand profile)"""
        self.logoutCurrentUser()
        self.setup_media()
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        for filename, manifest in manifests.manifest.iteritems():
            if 'odvod' not in manifest.supported_modes():
                continue
            baseurl = self.from_uri(
                'dash-mpd-v3',
                mode='odvod',
                manifest=filename,
                stream='bbb')
            response = self.app.get(baseurl)
            self.assertIn(
                "urn:mpeg:dash:profile:isoff-on-demand:2011",
                response.xml.get('profiles'))
            mpd = ViewsTestDashValidator(
                self.app, "odvod", response.xml, baseurl)
            mpd.validate()

    def test_request_unknown_media(self):
        url = self.from_uri(
            "dash-media",
            mode="vod",
            filename="notfound",
            segment_num=1,
            ext="mp4")
        self.app.get(url, status=404)

    def test_playready_la_url(self):
        """
        PlayReady LA_URL in the manifest
        """
        # TODO: don't hard code KID
        test_la_url = PlayReady.TEST_LA_URL.format(
            cfgs='(kid:QFS0GixTmUOU3Fxa2VhLrA==,persist:false,sl:150)')
        self.check_playready_la_url_value(test_la_url, [])

    def test_playready_la_url_override(self):
        """
        Replace LA_URL in stream with CGI playready_la_url parameter
        """
        test_la_url = 'https://licence.url.override/'
        self.check_playready_la_url_value(
            test_la_url,
            ['playready_la_url={0}'.format(urllib.quote_plus(test_la_url))])

    def check_playready_la_url_value(self, test_la_url, args):
        """
        Check the LA_URL in the PRO element is correct
        """
        self.setup_media()
        self.logoutCurrentUser()
        filename = 'hand_made.mpd'
        baseurl = self.from_uri('dash-mpd-v2', manifest=filename, stream='bbb')
        args += ['mode=vod', 'drm=playready']
        baseurl += '?' + '&'.join(args)
        response = self.app.get(baseurl)
        mpd = ViewsTestDashValidator(self.app, 'vod', response.xml, baseurl)
        mpd.validate()
        self.assertEqual(len(mpd.manifest.periods), 1)
        schemeIdUri = "urn:uuid:" + PlayReady.SYSTEM_ID.upper()
        pro_tag = "{{{0}}}pro".format(mpd.xmlNamespaces['mspr'])
        for adap_set in mpd.manifest.periods[0].adaptation_sets:
            for prot in adap_set.contentProtection:
                if prot.schemeIdUri != schemeIdUri:
                    continue
                for elt in prot.children:
                    if elt.tag != pro_tag:
                        continue
                    pro = base64.b64decode(elt.text)
                    for record in PlayReady.parse_pro(
                            utils.BufferedReader(None, data=pro)):
                        la_urls = record['xml'].findall(
                            './prh:DATA/prh:LA_URL', mpd.xmlNamespaces)
                        self.assertEqual(len(la_urls), 1)
                        self.assertEqual(la_urls[0].text, test_la_url)

    def test_injected_http_error_codes(self):
        self.setup_media()
        self.logoutCurrentUser()
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        for seg in range(1, 5):
            url = self.from_uri("dash-media", mode="vod",
                                filename=media_files[0].representation.id,
                                segment_num=seg, ext="mp4", absolute=True)
            response = self.app.get(url)
            self.assertEqual(response.status_int, 200)
            for code in [404, 410, 503, 504]:
                if seg in [1, 3]:
                    status = code
                else:
                    status = 200
                self.app.get(url, {str(code): '1,3'}, status=status)

    def test_video_corruption(self):
        self.setup_media()
        self.logoutCurrentUser()
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        for seg in range(1, 5):
            url = self.from_uri("dash-media", mode="vod",
                                filename=media_files[0].representation.id,
                                segment_num=seg, ext="mp4", absolute=True)
            clean = self.app.get(url)
            corrupt = self.app.get(url, {'corrupt': '1,2'})
            if seg < 3:
                self.assertNotEqual(clean.body, corrupt.body)
            else:
                self.assertEqual(clean.body, corrupt.body)


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            TestHandlers)

if __name__ == '__main__':
    unittest.main()
