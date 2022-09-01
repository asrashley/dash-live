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
from functools import wraps
import json
import logging
import os
import unittest
try:
    from unittest import mock
except ImportError:
    # use Python 2 back-port
    import mock
import urlparse
import urllib
import sys

_src = os.path.join(os.path.dirname(__file__), "..", "src")
if _src not in sys.path:
    sys.path.append(_src)

# these imports *must* be after the modification of sys.path
from mixins import TestCaseMixin, HideMixinsFilter
import dash
import events
import routes
import manifests
import utils
import views
import mp4
import models
import scte35
from drm.playready import PlayReady
from mpeg import MPEG_TIMEBASE
from gae_base import GAETestBase

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


class TestHandlers(GAETestBase):
    def test_index_page(self):
        self.setup_media()
        page = views.MainPage()
        self.assertIsNotNone(getattr(page, 'get', None))
        url = self.from_uri('home', absolute=True)
        self.logoutCurrentUser()
        response = self.app.get(url)
        self.assertEqual(response.status_int, 200)
        response.mustcontain(
            'Log In', no='href="{}"'.format(
                self.from_uri('media-index')))
        for filename, manifest in manifests.manifest.iteritems():
            mpd_url = self.from_uri('dash-mpd-v3', manifest=filename, stream='placeholder',
                                    mode='live')
            mpd_url = mpd_url.replace('/placeholder/', '/{directory}/')
            mpd_url = mpd_url.replace('/live/', '/{mode}/')
            response.mustcontain(mpd_url)
        self.setCurrentUser(is_admin=True)
        response = self.app.get(url)
        self.assertEqual(response.status_int, 200)
        response.mustcontain(
            'href="{}"'.format(
                self.from_uri('media-index')),
            no="Log In")
        response.mustcontain('Log Out')
        # self.setCurrentUser(is_admin=False)
        # response = self.app.get(url)
        # response.mustcontain('<a href="',mpd_url, no=routes.routes['upload'].title)

    def test_media_page(self):
        self.setup_media()
        page = views.MediaHandler()
        self.assertIsNotNone(getattr(page, 'get', None))
        self.assertIsNotNone(getattr(page, 'post', None))
        url = self.from_uri('media-index', absolute=True)

        # user must be logged in to use media page
        self.logoutCurrentUser()
        response = self.app.get(url, status=401)
        self.assertEqual(response.status_int, 401)

        # user must be logged in as admin to use media page
        self.setCurrentUser(is_admin=False)
        response = self.app.get(url, status=401)
        self.assertEqual(response.status_int, 401)

        # user must be logged in as admin to use media page
        self.setCurrentUser(is_admin=True)
        response = self.app.get(url)
        self.assertEqual(response.status_int, 200)

    def check_manifest(self, filename, indexes, tested):
        params = {}
        mode = None
        for idx, option in enumerate(self.cgi_options):
            name, values = option
            value = values[indexes[idx]]
            if name == 'mode':
                mode = value[5:]
            elif value:
                params[name] = value
        # remove pointless combinations of options
        if mode not in manifests.manifest[filename]['modes']:
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

    def check_a_manifest_using_all_options(self, filename, manifest):
        """
        Exhaustive test of a manifest with every combination of options.
        This test is _very_ slow, expect it to take several minutes!
        """
        self.setup_media()
        self.logoutCurrentUser()
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        # do a first pass check with no CGI options
        for mode in ['vod', 'live', 'odvod']:
            if mode not in manifest['modes']:
                continue
            url = self.from_uri(
                'dash-mpd-v3',
                manifest=filename,
                mode=mode,
                stream='bbb')
            response = self.app.get(url)
            TestCaseMixin._orig_assert_true = TestCaseMixin._assert_true
            TestCaseMixin._assert_true = add_url(
                TestCaseMixin._assert_true, url)
            mpd = ViewsTestDashValidator(self.app, mode, response.xml, url)
            mpd.validate(depth=2)
            TestCaseMixin._assert_true = TestCaseMixin._orig_assert_true
            del TestCaseMixin._orig_assert_true

        # do the exhaustive check of every option
        total_tests = 1
        count = 0
        for param in self.cgi_options:
            total_tests = total_tests * len(param[1])
        tested = set([url])
        indexes = [0] * len(self.cgi_options)
        done = False
        while not done:
            self.progress(count, total_tests)
            count += 1
            self.check_manifest(filename, indexes, tested)
            idx = 0
            while idx < len(self.cgi_options):
                indexes[idx] += 1
                if indexes[idx] < len(self.cgi_options[idx][1]):
                    break
                indexes[idx] = 0
                idx += 1
            if idx == len(self.cgi_options):
                done = True
        self.progress(total_tests, total_tests)

    def test_availability_start_time(self):
        """Control of MPD@availabilityStartTime using the start parameter"""
        self.setup_media()
        self.logoutCurrentUser()
        drm_options = None
        for o in self.cgi_options:
            if o[0] == 'drm':
                drm_options = o[1]
                break
        self.assertIsNotNone(drm_options)
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        filename = 'hand_made.mpd'
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
        drm_options = None
        for o in self.cgi_options:
            if o[0] == 'drm':
                drm_options = o[1]
                break
        self.assertIsNotNone(drm_options)
        # pr = drm.PlayReady(self.templates)
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        total_tests = len(drm_options)
        test_count = 0
        filename = 'hand_made.mpd'
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
        drm_options = None
        for o in self.cgi_options:
            if o[0] == 'drm':
                drm_options = o[1]
                break
        self.assertIsNotNone(drm_options)
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        total_tests = len(drm_options) * len(PlayReady.MAJOR_VERSIONS)
        test_count = 0
        filename = 'hand_made.mpd'
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
            if 'odvod' not in manifest['modes']:
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

    def test_inline_ping_pong_dash_events(self):
        """
        Test DASH 'PingPong' events carried in the manifest
        """
        self.logoutCurrentUser()
        self.setup_media()
        params = {
            'events': 'ping',
            'ping_count': '4',
            'ping_inband': '0',
            'ping_start': '256',
        }
        url = self.from_uri(
            'dash-mpd-v3',
            manifest='hand_made.mpd',
            mode='vod',
            stream='bbb',
            params=params)
        dv = self.check_manifest_url(url, 'vod')
        for period in dv.manifest.periods:
            self.assertEqual(len(period.event_streams), 1)
            event_stream = period.event_streams[0]
            self.assertEqual(event_stream.schemeIdUri, events.PingPong.schemeIdUri)
            self.assertEqual(event_stream.value, events.PingPong.PARAMS['value'])
            self.assertIsInstance(event_stream, dash.EventStream)
            self.assertEqual(len(event_stream.events), 4)
            presentationTime = 256
            for idx, event in enumerate(event_stream.events):
                self.assertEqual(event.id, idx)
                self.assertEqual(event.presentationTime, presentationTime)
                self.assertEqual(event.duration, events.PingPong.PARAMS['duration'])
                presentationTime += events.PingPong.PARAMS['interval']

    def test_inband_ping_pong_dash_events(self):
        """
        Test DASH 'PingPong' events carried in the video media segments
        """
        self.logoutCurrentUser()
        self.setup_media()
        params = {
            'events': 'ping',
            'ping_count': 4,
            'ping_inband': True,
            'ping_start': 200,
        }
        url = self.from_uri(
            'dash-mpd-v3',
            manifest='hand_made.mpd',
            mode='vod',
            stream='bbb',
            params=params)
        dv = self.check_manifest_url(url, 'vod')
        for period in dv.manifest.periods:
            for adp in period.adaptation_sets:
                if adp.contentType != 'video':
                    continue
                self.assertEqual(len(adp.event_streams), 1)
                event_stream = adp.event_streams[0]
                self.assertEqual(event_stream.schemeIdUri, events.PingPong.schemeIdUri)
                self.assertEqual(event_stream.value, events.PingPong.PARAMS['value'])
                self.assertIsInstance(event_stream, dash.InbandEventStream)
                rep = adp.representations[0]
                info = dv.get_representation_info(rep)
                self.check_inband_events_for_representation(rep, params, info)

    def check_inband_events_for_representation(self, rep, params, info):
        """
        Check all of the fragments in the given representation
        """
        rep.validate(depth=0)
        ev_presentation_time = params['ping_start']
        event_id = 0
        for seg in rep.media_segments:
            # print(seg.url)
            frag = mp4.Wrapper(
                atom_type='wrap',
                children=seg.validate(depth=1, all_atoms=True))
            seg_presentation_time = (
                ev_presentation_time * info.timescale /
                events.PingPong.PARAMS['timescale'])
            decode_time = frag.moof.traf.tfdt.base_media_decode_time
            seg_end = decode_time + seg.duration
            if seg_presentation_time < decode_time or seg_presentation_time >= seg_end:
                # check that there are no emsg boxes in fragment
                with self.assertRaises(AttributeError):
                    emsg = frag.emsg
                continue
            delta = seg_presentation_time - decode_time
            delta = (delta * events.PingPong.PARAMS['timescale'] /
                     info.timescale)
            emsg = frag.emsg
            self.assertEqual(emsg.scheme_id_uri, events.PingPong.schemeIdUri)
            self.assertEqual(emsg.value, events.PingPong.PARAMS['value'])
            self.assertEqual(emsg.presentation_time_delta, delta)
            self.assertEqual(emsg.event_id, event_id)
            if (event_id & 1) == 0:
                self.assertEqual(emsg.data, 'ping')
            else:
                self.assertEqual(emsg.data, 'pong')
            ev_presentation_time += events.PingPong.PARAMS['interval']
            event_id += 1

    def test_inline_scte35_dash_events(self):
        """
        Test DASH scte35 events carried in the manifest
        """
        self.logoutCurrentUser()
        self.setup_media()
        params = {
            'events': 'scte35',
            'scte35_count': '4',
            'scte35_inband': '0',
            'scte35_start': '256',
            'scte35_program_id': '345',
        }
        url = self.from_uri(
            'dash-mpd-v3',
            manifest='hand_made.mpd',
            mode='vod',
            stream='bbb',
            params=params)
        dv = self.check_manifest_url(url, 'vod')
        dv.validate()
        for period in dv.manifest.periods:
            self.assertEqual(len(period.event_streams), 1)
            event_stream = period.event_streams[0]
            self.assertEqual(event_stream.schemeIdUri, events.Scte35.schemeIdUri)
            self.assertEqual(event_stream.value, events.Scte35.PARAMS['value'])
            self.assertIsInstance(event_stream, dash.EventStream)
            self.assertEqual(len(event_stream.events), 4)
            presentationTime = 256
            for idx, event in enumerate(event_stream.events):
                self.assertEqual(event.id, idx)
                self.assertEqual(event.presentationTime, presentationTime)
                self.assertEqual(event.duration, events.Scte35.PARAMS['duration'])
                auto_return = (idx & 1) == 0
                avail_num = idx // 2
                expected = {
                    'table_id': 0xFC,
                    'private_indicator': False,
                    'protocol_version': 0,
                    'encrypted_packet': False,
                    'splice_command_type': 5,
                    'splice_insert': {
                        'avail_num': avail_num,
                        'break_duration': {
                            'auto_return': auto_return,
                            'duration': int(round(event.duration * MPEG_TIMEBASE / event_stream.timescale))
                        },
                        'splice_time': {
                            'pts': int(round(event.presentationTime * MPEG_TIMEBASE / event_stream.timescale))
                        },
                        'out_of_network_indicator': True,
                        'splice_event_cancel_indicator': False,
                        'splice_immediate_flag': False,
                        'unique_program_id': 345,
                    },
                    'descriptors': [{
                        "segment_num": 0,
                        "tag": 2,
                        "web_delivery_allowed_flag": True,
                        "segmentation_type_id": 0x34 + (idx & 1),
                        "device_restrictions": 3,
                        "archive_allowed_flag": True,
                        "components": None,
                        "segmentation_event_id": avail_num,
                        "segmentation_duration": 0,
                        "no_regional_blackout_flag": True,
                        "segmentation_event_cancel_indicator": False,
                        "segmentation_duration_flag": True,
                        "delivery_not_restricted_flag": True,
                        "segments_expected": 0,
                        "program_segmentation_flag": True,
                        "segmentation_upid_type": 15,
                        "identifier": scte35.descriptors.SegmentationDescriptor.IDENTIFIER,
                    }],
                }
                # print(json.dumps(event.scte35_binary_signal, indent=2))
                self.assertObjectEqual(expected, event.scte35_binary_signal)
                presentationTime += events.Scte35.PARAMS['interval']

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

    @staticmethod
    def cgi_combinations(cgi_options):
        """convert a list of CGI options into a set of all possible combinations"""
        indexes = [0] * len(cgi_options)
        result = set()
        done = False
        while not done:
            params = {}
            mode = None
            for idx, option in enumerate(cgi_options):
                name, values = option
                value = values[indexes[idx]]
                if name == 'mode':
                    mode = value[5:]
                if value:
                    params[name] = value
            if mode in manifests.manifest[filename]['modes']:
                if mode != "live":
                    if "mup" in params:
                        del params["mup"]
                    if "time" in params:
                        del params["time"]
                cgi = '&'.join(params.values())
                result.add(cgi)
            idx = 0
            while idx < len(cgi_options):
                indexes[idx] += 1
                if indexes[idx] < len(cgi_options[idx][1]):
                    break
                indexes[idx] = 0
                idx += 1
            if idx == len(cgi_options):
                done = True
        return result

    def test_video_playback(self):
        """Test generating the video HTML page.
        Checks every manifest with every CGI parameter causes a valid
        HTML page that allows the video to be watched using a <video> element.
        """
        def opt_choose(item):
            return item[0] in ['mode', 'acodec', 'drm']

        self.setup_media()
        self.logoutCurrentUser()
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        url = self.from_uri("video", absolute=True)
        options = filter(opt_choose, self.cgi_options)
        options = self.cgi_combinations(options)
        num_tests = (len(options) * len(models.Stream.all()) *
                     len(manifests.manifest))
        count = 0
        for filename, manifest in manifests.manifest.iteritems():
            for stream in models.Stream.all():
                for opt in options:
                    html_url = url + '?mpd={prefix}/{mpd}&{opt}'.format(
                        prefix=stream.prefix, mpd=filename, opt=opt)
                    self.progress(count, num_tests)
                    response = self.app.get(html_url)
                    html = response.html
                    self.assertEqual(html.title.string, manifest['title'])
                    for script in html.find_all('script'):
                        if script.get("src"):
                            continue
                        script = script.get_text()
                        self.assertIn('var dashParameters', script)
                        start = script.index('{')
                        end = script.rindex('}') + 1
                        script = json.loads(script[start:end])
                        for field in ['title', 'prefix',
                                      'playready_la_url', 'marlin_la_url']:
                            self.assertEqual(
                                script['stream'][field], getattr(
                                    stream, field))
                    count += 1
        self.progress(num_tests, num_tests)


def gen_test_fn(filename, manifest):
    def run_test(self):
        self.check_a_manifest_using_all_options(filename, manifest)
    return run_test


for filename, manifest in manifests.manifest.iteritems():
    name = filename[:-4]  # remove '.mpd'
    if 'manifest' not in name:
        name = name + '_manifest'
    setattr(
        TestHandlers,
        "test_all_options_%s" %
        (name),
        gen_test_fn(
            filename,
            manifest))

if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            TestHandlers)

if __name__ == '__main__':
    unittest.main()
