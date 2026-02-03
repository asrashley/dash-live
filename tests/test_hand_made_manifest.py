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
from dashlive.server.options.utc_time_options import UTCMethod
from dashlive.utils import objects

from .mixins.check_manifest import DashManifestCheckMixin
from .mixins.flask_base import FlaskTestBase
from .mixins.mock_time import MockTime
from .mixins.stream_fixtures import BBB_FIXTURE, MPS_FIXTURE, StreamFixture

class HandMadeManifestTests(FlaskTestBase, DashManifestCheckMixin):

    async def test_hand_made_manifest_live_abr(self):
        await self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'live', abr=True, now="2020-10-07T09:59:02Z",
            only={'audioCodec', 'minimumupdateperiod'})

    async def check_utc_timing_methods(self, mps: bool):
        url: str
        fixture: StreamFixture
        if mps:
            self.setup_multi_period_stream(MPS_FIXTURE)
            fixture = MPS_FIXTURE
            url = flask.url_for(
                'mps-manifest', manifest='hand_made.mpd', mode='live', mps_name=fixture.name)
        else:
            fixture = BBB_FIXTURE
            self.setup_media_fixture(fixture, with_subs=False)
            url = flask.url_for(
                'dash-mpd-v3', manifest='hand_made.mpd', mode='live', stream=fixture.name)

        self.logout_user()
        self.assertGreaterThan(models.MediaFile.count(), 0)

        assert UTCMethod.cgi_choices is not None
        for method in UTCMethod.cgi_choices:
            if method is None:
                continue
            query: str = f'?time={method}'
            with self.subTest(method=method, url=url):
                await self.check_manifest_using_options(
                    'live', url, query, debug=False, check_media=False,
                    check_head=False, now='2026-01-02T03:04:05Z', duration=(fixture.segment_duration * 2),
                    fixture=fixture)

    async def test_utc_timing_methods_std_manifest(self):
        await self.check_utc_timing_methods(False)

    async def test_utc_timing_methods_mps_manifest(self):
        await self.check_utc_timing_methods(True)

    async def test_legacy_vod_manifest_name(self):
        self.setup_media_fixture(BBB_FIXTURE)
        url = flask.url_for('dash-mpd-v1', manifest='manifest_vod.mpd')
        await self.check_manifest_url(
            url, mode="vod", encrypted=False, check_head=True, debug=False,
            check_media=False, duration=(2 * BBB_FIXTURE.segment_duration),
            now='2024-09-03T10:07:00Z', fixture=BBB_FIXTURE)

    async def test_legacy_encrypted_manifest_name_vod(self):
        self.setup_media_fixture(BBB_FIXTURE)
        url = flask.url_for('dash-mpd-v1', manifest='enc.mpd')
        await self.check_manifest_url(
            url, mode="vod", encrypted=True, check_head=True, check_media=False,
            debug=False, duration=(2 * BBB_FIXTURE.segment_duration),
            now='2024-09-03T10:07:00Z', fixture=BBB_FIXTURE)

    async def test_legacy_encrypted_manifest_name_live(self):
        self.setup_media_fixture(BBB_FIXTURE)
        url = flask.url_for('dash-mpd-v1', manifest='enc.mpd')
        url += '?mode=live'
        with MockTime("2020-10-07T09:59:02Z"):
            await self.check_manifest_url(
                url, mode="live", encrypted=True, check_head=True,
                check_media=False, debug=False,
                duration=(2 * BBB_FIXTURE.segment_duration),
                now='2024-09-03T10:07:00Z', fixture=BBB_FIXTURE)

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
        self.setup_media_fixture(BBB_FIXTURE, with_subs=with_subs)
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
            stream=BBB_FIXTURE.name)
        drm_checks = ['none'] + DrmSystem.values()
        for drm in drm_checks:
            args['drm'] = drm
            options = OptionsRepository.convert_cgi_options(args, defaults=defaults)
            params = options.generate_cgi_parameters(exclude={'mode'})
            query = objects.dict_to_cgi_params(params)
            await self.check_manifest_using_options(
                mode='live', url=url, query=query, debug=False,
                now="2023-09-06T09:59:02Z", duration=45,
                check_media=True, check_head=False, fixture=BBB_FIXTURE)


if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
