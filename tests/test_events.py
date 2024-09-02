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

import os
import unittest

import flask

from dashlive import scte35
from dashlive.mpeg import MPEG_TIMEBASE, mp4
from dashlive.server.events.ping_pong import PingPongEvents
from dashlive.server.events.scte35_events import Scte35Events
from dashlive.utils.buffered_reader import BufferedReader

from .mixins.flask_base import FlaskTestBase
from .mixins.check_manifest import DashManifestCheckMixin

class TestDashEventGeneration(DashManifestCheckMixin, FlaskTestBase):
    async def test_inline_ping_pong_dash_events(self):
        """
        Test DASH 'PingPong' events carried in the manifest
        """
        self.logout_user()
        self.setup_media()
        params = {
            'events': 'ping',
            'ping_count': '4',
            'ping_inband': '0',
            'ping_start': '256',
        }
        url = flask.url_for(
            'dash-mpd-v3',
            manifest='hand_made.mpd',
            mode='vod',
            stream=self.FIXTURES_PATH.name,
            **params)
        dv = await self.check_manifest_url(
            url, mode='vod', encrypted=False, check_media=False, check_head=False,
            debug=False, duration=self.SEGMENT_DURATION,
            now='2024-09-03T10:07:00Z')
        for period in dv.manifest.periods:
            self.assertEqual(len(period.event_streams), 1)
            event_stream = period.event_streams[0]
            self.assertEqual(event_stream.schemeIdUri, PingPongEvents.schemeIdUri)
            self.assertEqual(event_stream.value, PingPongEvents.DEFAULT_VALUES['value'])
            # self.assertIsInstance(event_stream, EventStream)
            self.assertEqual(len(event_stream.events), 4)
            presentationTime = 256
            for idx, event in enumerate(event_stream.events):
                self.assertEqual(event.id, idx)
                self.assertEqual(event.presentationTime, presentationTime)
                self.assertEqual(event.duration, PingPongEvents.DEFAULT_VALUES['duration'])
                presentationTime += PingPongEvents.DEFAULT_VALUES['interval']

    async def test_inband_ping_pong_dash_events(self) -> None:
        """
        Test DASH 'PingPong' events carried in the video media segments
        """
        self.logout_user()
        self.setup_media()
        params = {
            'events': 'ping',
            'ping_count': 4,
            'ping_inband': True,
            'ping_start': 200,
        }
        url = flask.url_for(
            'dash-mpd-v3',
            manifest='hand_made.mpd',
            mode='vod',
            stream=self.FIXTURES_PATH.name,
            **params)
        dv = await self.check_manifest_url(
            url, 'vod', encrypted=False, check_media=True, check_head=False,
            debug=False, now='2024-09-03T10:07:00Z',
            duration=int(self.MEDIA_DURATION // 2))
        for period in dv.manifest.periods:
            for adp in period.adaptation_sets:
                if adp.contentType != 'video':
                    continue
                self.assertEqual(len(adp.event_streams), 1)
                event_stream = adp.event_streams[0]
                self.assertEqual(event_stream.schemeIdUri, PingPongEvents.schemeIdUri)
                self.assertEqual(event_stream.value, PingPongEvents.DEFAULT_VALUES['value'])
                # self.assertIsInstance(event_stream, InbandEventStream)
                rep = adp.representations[0]
                await self.check_inband_events_for_representation(rep, params)

    async def check_inband_events_for_representation(self, rep, params) -> None:
        """
        Check all of the fragments in the given representation
        """
        await rep.validate()
        ev_presentation_time = params['ping_start']
        event_id = 0
        for seg in rep.media_segments:
            if not seg.validated:
                continue
            # print(seg.url)
            response = self.client.get(seg.url)
            src = BufferedReader(None, data=response.get_data(as_text=False))
            options = {"strict": True}
            frag = mp4.Wrapper(
                atom_type='wrap',
                children=mp4.Mp4Atom.load(src, options=options))
            seg_presentation_time = (ev_presentation_time * rep.info.timescale /
                                     float(PingPongEvents.DEFAULT_VALUES['timescale']))
            first_sample_pos = frag.moof.traf.tfhd.base_data_offset + frag.moof.traf.trun.data_offset
            self.assertGreaterOrEqual(
                first_sample_pos, frag.mdat.position + frag.mdat.header_size)
            decode_time = frag.moof.traf.tfdt.base_media_decode_time
            seg_end = decode_time + seg.duration
            if seg_presentation_time < decode_time or seg_presentation_time >= seg_end:
                # check that there are no emsg boxes in fragment
                with self.assertRaises(AttributeError):
                    emsg = frag.emsg
                continue
            delta = seg_presentation_time - decode_time
            delta = (delta * PingPongEvents.DEFAULT_VALUES['timescale'] /
                     float(rep.info.timescale))
            emsg = frag.emsg
            self.assertEqual(emsg.scheme_id_uri, PingPongEvents.schemeIdUri)
            self.assertEqual(emsg.value, PingPongEvents.DEFAULT_VALUES['value'])
            self.assertEqual(emsg.presentation_time_delta, delta)
            self.assertEqual(emsg.event_id, event_id)
            if (event_id & 1) == 0:
                self.assertEqual(emsg.data, b'ping')
            else:
                self.assertEqual(emsg.data, b'pong')
            ev_presentation_time += PingPongEvents.DEFAULT_VALUES['interval']
            event_id += 1

    async def test_inline_scte35_dash_events(self) -> None:
        """
        Test DASH scte35 events carried in the manifest
        """
        self.logout_user()
        self.setup_media()
        params = {
            'events': 'scte35',
            'scte35_count': '4',
            'scte35_inband': '0',
            'scte35_start': '256',
            'scte35_program_id': '345',
        }
        url = flask.url_for(
            'dash-mpd-v3',
            manifest='hand_made.mpd',
            mode='vod',
            stream=self.FIXTURES_PATH.name,
            **params)
        dv = await self.check_manifest_url(
            url, 'vod', encrypted=False, check_media=False, check_head=False,
            debug=False, now='2024-09-03T10:07:00Z',
            duration=self.SEGMENT_DURATION)
        for period in dv.manifest.periods:
            self.assertEqual(len(period.event_streams), 1)
            event_stream = period.event_streams[0]
            self.assertEqual(event_stream.schemeIdUri, Scte35Events.schemeIdUri)
            self.assertEqual(event_stream.value, Scte35Events.DEFAULT_VALUES['value'])
            # self.assertIsInstance(event_stream, EventStream)
            self.assertEqual(len(event_stream.events), 4)
            presentationTime = 256
            for idx, event in enumerate(event_stream.events):
                self.assertEqual(event.id, idx)
                self.assertEqual(event.presentationTime, presentationTime)
                self.assertEqual(event.duration, Scte35Events.DEFAULT_VALUES['duration'])
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
                self.assertEqual(len(event.children()), 1)
                ev_elt = event.children()[0]
                self.assertEqual(len(ev_elt.children()), 1)
                self.assertObjectEqual(expected, ev_elt.children()[0].signal)
                presentationTime += Scte35Events.DEFAULT_VALUES['interval']


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            TestDashEventGeneration)

if __name__ == '__main__':
    unittest.main()
