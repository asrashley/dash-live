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

from .mixins.check_manifest import DashManifestCheckMixin
from .mixins.flask_base import FlaskTestBase

class ManifestAIVTest(FlaskTestBase, DashManifestCheckMixin):
    async def test_vod_manifest_aiv(self):
        await self.check_a_manifest_using_all_options('manifest_vod_aiv.mpd', 'odvod')

    def test_request_invalid_mode_for_manifest(self):
        baseurl = flask.url_for(
            'dash-mpd-v3', manifest='manifest_vod_aiv.mpd',
            stream=self.FIXTURES_PATH.name, mode='live')
        self.app.get(baseurl, status=404)

    def test_generated_manifest_against_fixture(self):
        self.check_generated_manifest_against_fixture(
            'manifest_vod_aiv.mpd', mode='vod', acodec='mp4a', encrypted=False,
            now="2023-10-05T20:19:58Z")


if __name__ == '__main__':
    unittest.main()
