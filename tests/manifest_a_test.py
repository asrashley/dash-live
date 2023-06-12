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
from __future__ import absolute_import
import os
import unittest

from tests.mixins.check_manifest import DashManifestCheckMixin
from tests.gae_base import GAETestBase

class ManifestATest(GAETestBase, DashManifestCheckMixin):
    def test_manifest_a(self):
        self.check_a_manifest_using_major_options('manifest_a.mpd')


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            ManifestATest)

if __name__ == '__main__':
    unittest.main()
