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
    def test_hand_made_manifest_vod(self):
        self.check_a_manifest_using_all_options('hand_made.mpd', 'vod', with_subs=True)

    def test_hand_made_manifest_live(self):
        self.check_a_manifest_using_all_options('hand_made.mpd', 'live', with_subs=True)

    def test_hand_made_manifest_vod_abr(self):
        self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'vod', only={'abr', 'audioCodec'})

    def test_hand_made_manifest_live_abr(self):
        self.check_a_manifest_using_all_options(
            'hand_made.mpd', 'live', only={'abr', 'audioCodec', 'minimumupdateperiod'})

    def test_hand_made_manifest_odvod(self):
        self.check_a_manifest_using_all_options('hand_made.mpd', 'odvod', with_subs=True)

    def test_legacy_vod_manifest_name(self):
        self.setup_media()
        url = flask.url_for('dash-mpd-v1', manifest='manifest_vod.mpd')
        self.check_manifest_url(url, mode="vod", encrypted=False, check_head=True)

    def test_legacy_encrypted_manifest_name(self):
        self.setup_media()
        url = flask.url_for('dash-mpd-v1', manifest='enc.mpd')
        self.check_manifest_url(url, mode="vod", encrypted=True, check_head=True)
        url += '?mode=live'
        self.check_manifest_url(url, mode="live", encrypted=True, check_head=True)

    @FlaskTestBase.mock_datetime_now(from_isodatetime("2022-09-06T15:10:02Z"))
    def test_generated_manifest_against_fixture(self):
        self.check_generated_manifest_against_fixture(
            'hand_made.mpd', mode='vod', acodec='mp4a')

    @FlaskTestBase.mock_datetime_now(from_isodatetime("2022-09-06T15:10:00Z"))
    def test_generated_drm_manifest_against_fixture(self):
        self.check_generated_manifest_against_fixture(
            'hand_made.mpd', mode='vod', drm='all',
            acodec='mp4a')

    @FlaskTestBase.mock_datetime_now(from_isodatetime("2022-09-06T15:10:02Z"))
    def test_generated_live_manifest_against_fixture(self):
        self.check_generated_manifest_against_fixture(
            'hand_made.mpd', mode='live', acodec='mp4a', time='xsd')

    @FlaskTestBase.mock_datetime_now(from_isodatetime("2022-09-06T15:10:00Z"))
    def test_generated_live_drm_manifest_against_fixture(self):
        self.check_generated_manifest_against_fixture(
            'hand_made.mpd', mode='live', drm='all',
            acodec='mp4a', time='xsd')


if __name__ == '__main__':
    unittest.main()
