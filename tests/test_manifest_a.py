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

from .mixins.check_manifest import DashManifestCheckMixin
from .mixins.flask_base import FlaskTestBase

class ManifestATest(FlaskTestBase, DashManifestCheckMixin):
    async def test_manifest_a_vod(self):
        await self.check_a_manifest_using_major_options('manifest_a.mpd', 'vod')

    async def test_manifest_a_live(self):
        await self.check_a_manifest_using_major_options(
            'manifest_a.mpd', 'live', debug=False, now="2023-10-25T07:56:58Z")

    def test_generated_manifest_against_fixture_vod(self):
        self.check_generated_manifest_against_fixture(
            'manifest_a.mpd', mode='vod', acodec='mp4a', encrypted=False,
            now="2023-10-25T07:56:58Z")

    def test_generated_manifest_against_fixture_live(self):
        self.check_generated_manifest_against_fixture(
            'manifest_a.mpd', mode='live', acodec='mp4a', encrypted=False,
            now="2023-10-25T07:56:58Z")


if __name__ == '__main__':
    unittest.main()
