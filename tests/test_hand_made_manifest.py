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
import logging
import unittest

import flask

from dashlive.drm.system import DrmSystem
from dashlive.server import models
from dashlive.server.options.repository import OptionsRepository
from dashlive.utils import objects

from .mixins.check_manifest import DashManifestCheckMixin
from .mixins.flask_base import FlaskTestBase
from .mixins.mock_time import MockTime

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

    async def test_hand_made_manifest_live_aac(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'live', with_subs=True, audioCodec='mp4a',
            segmentTimeline=False, now="2023-09-06T09:59:02Z")

    async def test_hand_made_manifest_live_ec3(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'live', with_subs=True, audioCodec='ec-3',
            segmentTimeline=False, now="2021-09-06T09:59:02Z")

    async def test_hand_made_manifest_live_all_audio(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'live', with_subs=True, audioCodec='any',
            segmentTimeline=False, now="2020-09-06T09:59:02Z")

    async def test_hand_made_manifest_live_aac_timeline(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'live', with_subs=True, audioCodec='mp4a',
            segmentTimeline=True, now="2023-09-06T09:59:02Z")

    async def test_hand_made_manifest_live_ec3_timeline(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'live', with_subs=True, audioCodec='ec-3',
            segmentTimeline=True, now="2021-09-06T09:59:02Z")

    async def test_hand_made_manifest_live_all_audio_timeline(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'live', with_subs=True, audioCodec='any',
            now="2020-09-06T09:59:02Z", segmentTimeline=True)

    async def test_hand_made_manifest_vod_abr(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'vod', only={'abr', 'audioCodec'})

    async def test_hand_made_manifest_live_abr(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'live', abr=True, now="2020-10-07T09:59:02Z",
            only={'audioCodec', 'minimumupdateperiod'})

    async def test_hand_made_manifest_odvod_aac(self):
        await self.check_a_manifest_using_major_options(
            'hand_made.mpd', 'odvod', with_subs=True, audioCodec='mp4a')

    async def test_hand_made_manifest_odvod_ec3(self):
        await self.check_a_manifest_using_major_options(
            'hand_made.mpd', 'odvod', with_subs=True, audioCodec='ec-3')

    async def test_hand_made_manifest_odvod_all_audio(self):
        await self.check_a_manifest_using_major_options(
            'hand_made.mpd', 'odvod', with_subs=True, audioCodec='any')

    async def test_legacy_vod_manifest_name(self):
        self.setup_media()
        url = flask.url_for('dash-mpd-v1', manifest='manifest_vod.mpd')
        await self.check_manifest_url(
            url, mode="vod", encrypted=False, check_head=True, debug=False,
            check_media=False, duration=(2 * self.SEGMENT_DURATION),
            now='2024-09-03T10:07:00Z')

    async def test_legacy_encrypted_manifest_name_vod(self):
        self.setup_media()
        url = flask.url_for('dash-mpd-v1', manifest='enc.mpd')
        await self.check_manifest_url(
            url, mode="vod", encrypted=True, check_head=True, check_media=False,
            debug=False, duration=(2 * self.SEGMENT_DURATION),
            now='2024-09-03T10:07:00Z')

    async def test_legacy_encrypted_manifest_name_live(self):
        self.setup_media()
        url = flask.url_for('dash-mpd-v1', manifest='enc.mpd')
        url += '?mode=live'
        with MockTime("2020-10-07T09:59:02Z"):
            await self.check_manifest_url(
                url, mode="live", encrypted=True, check_head=True,
                check_media=False, debug=False,
                duration=(2 * self.SEGMENT_DURATION),
                now='2024-09-03T10:07:00Z')

    def test_generated_vod_manifest_against_fixture(self):
        self.check_generated_manifest_against_fixture(
            'hand_made.mpd', mode='vod', acodec='mp4a', start='today', drm='none',
            encrypted=False, now="2022-09-06T15:10:02Z")

    def test_generated_vod_drm_manifest_against_fixture(self):
        self.check_generated_manifest_against_fixture(
            'hand_made.mpd', mode='vod', drm='all', encrypted=True,
            acodec='mp4a', start='today', now="2022-09-06T15:10:00Z")

    def test_generated_live_manifest_against_fixture(self):
        self.check_generated_manifest_against_fixture(
            'hand_made.mpd', mode='live', acodec='mp4a', time='xsd', start='today',
            now="2022-09-06T15:10:02Z", drm='none', encrypted=False)

    def test_generated_live_drm_manifest_against_fixture(self):
        self.check_generated_manifest_against_fixture(
            'hand_made.mpd', mode='live', drm='all', encrypted=True,
            now="2022-09-06T15:10:00Z",
            acodec='mp4a', time='http-ntp', start='today')

    async def test_manifest_patch_live(self):
        await self.check_manifest_patch_live(False)

    async def test_manifest_patch_live_with_subs(self):
        await self.check_manifest_patch_live(True)

    async def check_manifest_patch_live(self, with_subs: bool):
        self.setup_media(with_subs=with_subs)
        self.logout_user()
        self.assertGreaterThan(models.MediaFile.count(), 0)
        args = {
            'patch': '1',
            'abr': '0',
            'depth': '20',
            'drm': 'none',
            'timeline': '1',
        }
        defaults = OptionsRepository.get_default_options()
        url = flask.url_for(
            'dash-mpd-v3',
            manifest='hand_made.mpd',
            mode='live',
            stream=self.FIXTURES_PATH.name)
        drm_checks = ['none'] + DrmSystem.values()
        for drm in drm_checks:
            args['drm'] = drm
            options = OptionsRepository.convert_cgi_options(args, defaults=defaults)
            params = options.generate_cgi_parameters(exclude={'mode'})
            query = objects.dict_to_cgi_params(params)
            await self.check_manifest_using_options(
                mode='live', url=url, query=query, debug=False,
                now="2023-09-06T09:59:02Z", duration=45,
                check_media=True, check_head=False)


if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
