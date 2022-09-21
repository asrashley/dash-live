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

from mixins.check_manifest import DashManifestCheckMixin
from gae_base import GAETestBase

class ManifestAIVTest(GAETestBase, DashManifestCheckMixin):
    def test_vod_manifest_aiv(self):
        self.check_a_manifest_using_all_options('manifest_vod_aiv.mpd')

    def test_request_invalid_mode_for_manifest(self):
        baseurl = self.from_uri(
            'dash-mpd-v3', manifest='manifest_vod_aiv.mpd', stream='bbb', mode='live')
        self.app.get(baseurl, status=404)


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            ManifestAIVTest)

if __name__ == '__main__':
    unittest.main()
