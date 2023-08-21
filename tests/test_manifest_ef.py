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

from .mixins.check_manifest import DashManifestCheckMixin
from .flask_base import FlaskTestBase

class ManifestEFTest(FlaskTestBase, DashManifestCheckMixin):
    def test_manifest_ef_vod(self):
        self.check_a_manifest_using_major_options('manifest_ef.mpd', 'vod')

    def test_manifest_ef_live(self):
        self.check_a_manifest_using_major_options('manifest_ef.mpd', 'live')


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            ManifestEFTest)

if __name__ == '__main__':
    unittest.main()
