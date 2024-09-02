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

class ManifestNTests(FlaskTestBase, DashManifestCheckMixin):
    async def test_manifest_n_vod(self):
        await self.check_a_manifest_using_all_options('manifest_n.mpd', 'vod')

    async def test_manifest_n_live(self):
        await self.check_a_manifest_using_all_options(
            'manifest_n.mpd', 'live', now="2022-09-06T09:59:02Z")

    def test_generated_manifest_against_fixture(self):
        self.check_generated_manifest_against_fixture(
            'manifest_n.mpd', mode='vod', acodec='mp4a', encrypted=False,
            now="2022-09-06T09:59:02Z")

    def test_generated_drm_manifest_against_fixture(self):
        self.check_generated_manifest_against_fixture(
            'manifest_n.mpd', mode='vod', drm='all',
            acodec='mp4a', encrypted=True, now="2022-09-06T11:57:00Z")


if __name__ == '__main__':
    unittest.main()
