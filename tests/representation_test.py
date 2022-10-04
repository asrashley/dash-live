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

import io
import os
import sys
import unittest

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src not in sys.path:
    sys.path.append(_src)

# these imports *must* be after the modification of sys.path
from server import models
from mpeg.mp4 import Mp4Atom
from mpeg.dash.representation import Representation
from utils.buffered_reader import BufferedReader

from gae_base import GAETestBase

class RepresentationTests(GAETestBase, unittest.TestCase):
    def setUp(self):
        super(RepresentationTests, self).setUp()
        self.fixtures = os.path.join(os.path.dirname(__file__), "fixtures")

    def test_load_representation(self):
        self.setup_media()
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        for mfile in media_files:
            filename = os.path.join(self.fixtures, mfile.name)
            src = BufferedReader(io.FileIO(filename, 'rb'))
            atoms = Mp4Atom.load(src)
            rep = Representation.load(filename, atoms)
            expected = rep.toJSON()
            actual = mfile.representation.toJSON()
            self.assertObjectEqual(expected, actual)


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            RepresentationTests)

if __name__ == "__main__":
    unittest.main()
