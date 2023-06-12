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
from __future__ import absolute_import
import os
import sys
import unittest

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src not in sys.path:
    sys.path.append(_src)

# these imports *must* be after the modification of sys.path
from mpeg import MPEG_TIMEBASE, mp4
from tests.gae_base import GAETestBase
from tests.mixins.check_manifest import DashManifestCheckMixin
from tests.dash_validator import EventStream, InbandEventStream
from server.events.ping_pong import PingPongEvents
from server.events.scte35_events import Scte35Events
import scte35

class TestDashEventGeneration(DashManifestCheckMixin, GAETestBase):
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
        dv = self.check_manifest_url(url, 'vod', encrypted=False)
        for period in dv.manifest.periods:
            self.assertEqual(len(period.event_streams), 1)
            event_stream = period.event_streams[0]
            self.assertEqual(event_stream.schemeIdUri, PingPongEvents.schemeIdUri)
            self.assertEqual(event_stream.value, PingPongEvents.PARAMS['value'])
            # self.assertIsInstance(event_stream, EventStream)
            self.assertEqual(len(event_stream.events), 4)
            presentationTime = 256
            for idx, event in enumerate(event_stream.events):
                self.assertEqual(event.id, idx)
                self.assertEqual(event.presentationTime, presentationTime)
                self.assertEqual(event.duration, PingPongEvents.PARAMS['duration'])
                presentationTime += PingPongEvents.PARAMS['interval']

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
        dv = self.check_manifest_url(url, 'vod', encrypted=False)
        for period in dv.manifest.periods:
            for adp in period.adaptation_sets:
                if adp.contentType != 'video':
                    continue
                self.assertEqual(len(adp.event_streams), 1)
                event_stream = adp.event_streams[0]
                self.assertEqual(event_stream.schemeIdUri, PingPongEvents.schemeIdUri)
                self.assertEqual(event_stream.value, PingPongEvents.PARAMS['value'])
                # self.assertIsInstance(event_stream, InbandEventStream)
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
                PingPongEvents.PARAMS['timescale'])
            decode_time = frag.moof.traf.tfdt.base_media_decode_time
            seg_end = decode_time + seg.duration
            if seg_presentation_time < decode_time or seg_presentation_time >= seg_end:
                # check that there are no emsg boxes in fragment
                with self.assertRaises(AttributeError):
                    emsg = frag.emsg
                continue
            delta = seg_presentation_time - decode_time
            delta = (delta * PingPongEvents.PARAMS['timescale'] /
                     info.timescale)
            emsg = frag.emsg
            self.assertEqual(emsg.scheme_id_uri, PingPongEvents.schemeIdUri)
            self.assertEqual(emsg.value, PingPongEvents.PARAMS['value'])
            self.assertEqual(emsg.presentation_time_delta, delta)
            self.assertEqual(emsg.event_id, event_id)
            if (event_id & 1) == 0:
                self.assertEqual(emsg.data, 'ping')
            else:
                self.assertEqual(emsg.data, 'pong')
            ev_presentation_time += PingPongEvents.PARAMS['interval']
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
        dv = self.check_manifest_url(url, 'vod', encrypted=False)
        dv.validate()
        for period in dv.manifest.periods:
            self.assertEqual(len(period.event_streams), 1)
            event_stream = period.event_streams[0]
            self.assertEqual(event_stream.schemeIdUri, Scte35Events.schemeIdUri)
            self.assertEqual(event_stream.value, Scte35Events.PARAMS['value'])
            # self.assertIsInstance(event_stream, EventStream)
            self.assertEqual(len(event_stream.events), 4)
            presentationTime = 256
            for idx, event in enumerate(event_stream.events):
                self.assertEqual(event.id, idx)
                self.assertEqual(event.presentationTime, presentationTime)
                self.assertEqual(event.duration, Scte35Events.PARAMS['duration'])
                auto_return = (idx & 1) == 0
                avail_num = 1 + (idx // 2)
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
                        "segmentation_type": 0x34 + (idx & 1),
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
                        "identifier": scte35.descriptors.SpliceDescriptor.CUE_IDENTIFIER,
                    }],
                }
                # print(json.dumps(event.scte35_binary_signal, indent=2))
                self.assertObjectEqual(expected, event.scte35_binary_signal)
                presentationTime += Scte35Events.PARAMS['interval']


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            TestDashEventGeneration)

if __name__ == '__main__':
    unittest.main()
