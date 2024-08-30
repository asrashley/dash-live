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
import unittest

import flask

from dashlive.utils.date_time import from_isodatetime

from .mixins.flask_base import FlaskTestBase
from .mixins.check_manifest import DashManifestCheckMixin

class HandMadeManifestTests(FlaskTestBase, DashManifestCheckMixin):
    async def test_hand_made_manifest_aac_vod(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'vod', with_subs=True, audioCodec='mp4a',
            segmentTimeline=False)

    async def test_hand_made_manifest_aac_vod_timeline(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'vod', with_subs=True, audioCodec='mp4a',
            segmentTimeline=True)

    async def test_hand_made_manifest_ec3_vod(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'vod', with_subs=True, audioCodec='ec-3',
            segmentTimeline=False)

    async def test_hand_made_manifest_ec3_vod_timeline(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'vod', with_subs=True, audioCodec='ec-3',
            segmentTimeline=True)

    async def test_hand_made_manifest_all_audio_codecs_vod(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'vod', with_subs=True, audioCodec='any',
            segmentTimeline=False)

    async def test_hand_made_manifest_all_audio_codecs_vod_timeline(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'vod', with_subs=True, audioCodec='any',
            segmentTimeline=True)

    @FlaskTestBase.mock_datetime_now(from_isodatetime("2023-09-06T09:59:02Z"))
    async def test_hand_made_manifest_live_aac(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'live', with_subs=True, audioCodec='mp4a',
            segmentTimeline=False)

    @FlaskTestBase.mock_datetime_now(from_isodatetime("2021-09-06T09:59:02Z"))
    async def test_hand_made_manifest_live_ec3(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'live', with_subs=True, audioCodec='ec-3',
            segmentTimeline=False)

    @FlaskTestBase.mock_datetime_now(from_isodatetime("2020-09-06T09:59:02Z"))
    async def test_hand_made_manifest_live_all_audio(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'live', with_subs=True, audioCodec='any',
            segmentTimeline=False)

    @FlaskTestBase.mock_datetime_now(from_isodatetime("2023-09-06T09:59:02Z"))
    async def test_hand_made_manifest_live_aac_timeline(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'live', with_subs=True, audioCodec='mp4a',
            segmentTimeline=True)

    @FlaskTestBase.mock_datetime_now(from_isodatetime("2021-09-06T09:59:02Z"))
    async def test_hand_made_manifest_live_ec3_timeline(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'live', with_subs=True, audioCodec='ec-3',
            segmentTimeline=True)

    @FlaskTestBase.mock_datetime_now(from_isodatetime("2020-09-06T09:59:02Z"))
    async def test_hand_made_manifest_live_all_audio_timeline(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'live', with_subs=True, audioCodec='any',
            segmentTimeline=True)

    async def test_hand_made_manifest_vod_abr(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'vod', only={'abr', 'audioCodec'})

    @FlaskTestBase.mock_datetime_now(from_isodatetime("2020-10-07T09:59:02Z"))
    async def test_hand_made_manifest_live_abr(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'live', abr=True, only={'audioCodec', 'minimumupdateperiod'})

    async def test_hand_made_manifest_odvod_aac(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'odvod', with_subs=True, audioCodec='mp4a')

    async def test_hand_made_manifest_odvod_ec3(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'odvod', with_subs=True, audioCodec='ec-3')

    async def test_hand_made_manifest_odvod_all_audio(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'odvod', with_subs=True, audioCodec='any')

    async def test_legacy_vod_manifest_name(self):
        self.setup_media()
        url = flask.url_for('dash-mpd-v1', manifest='manifest_vod.mpd')
        await self.check_manifest_url(
            url, mode="vod", encrypted=False, check_head=True, debug=False,
            check_media=False, duration=(2 * self.SEGMENT_DURATION))

    async def test_legacy_encrypted_manifest_name_vod(self):
        self.setup_media()
        url = flask.url_for('dash-mpd-v1', manifest='enc.mpd')
        await self.check_manifest_url(
            url, mode="vod", encrypted=True, check_head=True, check_media=False,
            debug=False, duration=(2 * self.SEGMENT_DURATION))

    @FlaskTestBase.mock_datetime_now(from_isodatetime("2020-10-07T09:59:02Z"))
    async def test_legacy_encrypted_manifest_name_live(self):
        self.setup_media()
        url = flask.url_for('dash-mpd-v1', manifest='enc.mpd')
        url += '?mode=live'
        await self.check_manifest_url(
            url, mode="live", encrypted=True, check_head=True, check_media=False,
            debug=False, duration=(2 * self.SEGMENT_DURATION))

    @FlaskTestBase.mock_datetime_now(from_isodatetime("2022-09-06T15:10:02Z"))
    def test_generated_vod_manifest_against_fixture(self):
        self.check_generated_manifest_against_fixture(
            'hand_made.mpd', mode='vod', acodec='mp4a', start='today', drm='none',
            encrypted=False)

    @FlaskTestBase.mock_datetime_now(from_isodatetime("2022-09-06T15:10:00Z"))
    def test_generated_vod_drm_manifest_against_fixture(self):
        self.check_generated_manifest_against_fixture(
            'hand_made.mpd', mode='vod', drm='all', encrypted=True,
            acodec='mp4a', start='today')

    @FlaskTestBase.mock_datetime_now(from_isodatetime("2022-09-06T15:10:02Z"))
    def test_generated_live_manifest_against_fixture(self):
        self.check_generated_manifest_against_fixture(
            'hand_made.mpd', mode='live', acodec='mp4a', time='xsd', start='today',
            drm='none', encrypted=False)

    @FlaskTestBase.mock_datetime_now(from_isodatetime("2022-09-06T15:10:00Z"))
    def test_generated_live_drm_manifest_against_fixture(self):
        self.check_generated_manifest_against_fixture(
            'hand_made.mpd', mode='live', drm='all', encrypted=True,
            acodec='mp4a', time='xsd', start='today')

    @FlaskTestBase.mock_datetime_now(from_isodatetime("2023-09-06T09:59:02Z"))
    async def test_manifest_patch_live_aac(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'live', simplified=True, audioCodec='mp4a',
            segmentTimeline=True, patch=True)


if __name__ == '__main__':
    unittest.main()
