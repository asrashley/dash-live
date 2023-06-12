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
from tests.gae_base import GAETestBase
from utils.buffered_reader import BufferedReader

class RepresentationTests(GAETestBase, unittest.TestCase):
    def setUp(self):
        super(RepresentationTests, self).setUp()
        self.fixtures = os.path.join(os.path.dirname(__file__), "fixtures")

    def test_load_representation(self):
        self.setup_media(with_subs=True)
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

    def test_load_ebu_tt_d(self):
        filename = os.path.join(self.fixtures, "ebuttd.mp4")
        src = BufferedReader(io.FileIO(filename, 'rb'))
        atoms = Mp4Atom.load(src)
        rep = Representation.load(filename, atoms)
        self.assertEqual(rep.contentType, 'text')
        self.assertEqual(rep.timescale, 200)
        self.assertEqual(rep.mimeType, 'application/ttml+xml')
        self.assertEqual(rep.codecs, 'im1t|etd1')

    def test_load_web_vtt(self):
        filename = os.path.join(self.fixtures, "bbb_t1.mp4")
        src = BufferedReader(io.FileIO(filename, 'rb'))
        atoms = Mp4Atom.load(src)
        rep = Representation.load(filename, atoms)
        self.assertEqual(rep.contentType, 'text')
        self.assertEqual(rep.timescale, 1000)
        self.assertEqual(rep.mimeType, 'text/vtt')
        self.assertEqual(rep.codecs, 'wvtt')
        self.assertEqual(rep.mediaDuration, 39868)
        self.assertEqual(rep.encrypted, False)
        # 1 init segment + 3 media segments
        self.assertEqual(len(rep.segments), 4)

    def test_load_hevc(self):
        filename = os.path.join(self.fixtures, "hevc-rep.mp4")
        with open(filename, "rb") as f:
            src_data = f.read()
            src = BufferedReader(None, data=src_data)
        atoms = Mp4Atom.load(src)
        rep = Representation.load(filename, atoms)
        self.assertEqual(rep.contentType, 'video')
        self.assertEqual(rep.timescale, 600)
        self.assertEqual(rep.frameRate, 24)
        self.assertEqual(rep.mimeType, 'video/mp4')
        self.assertEqual(rep.codecs, 'hev1.2.4.L93.90')
        self.assertEqual(rep.width, 1280)
        self.assertEqual(rep.height, 544)
        self.assertEqual(rep.segment_duration, 1200)
        self.assertEqual(rep.mediaDuration, 6 * 600)
        self.assertEqual(rep.encrypted, False)
        self.assertEqual(rep.nalLengthFieldLength, 4)
        self.assertEqual(rep.lang, "eng")

    def test_load_ac3(self):
        filename = os.path.join(self.fixtures, "ac3-rep.mp4")
        with open(filename, "rb") as f:
            src_data = f.read()
            src = BufferedReader(None, data=src_data)
        atoms = Mp4Atom.load(src)
        rep = Representation.load(filename, atoms)
        self.assertEqual(rep.contentType, 'audio')
        self.assertEqual(rep.timescale, 48000)
        self.assertEqual(rep.mimeType, 'audio/mp4')
        self.assertEqual(rep.codecs, 'ac-3')
        self.assertEqual(rep.segment_duration, 2 * 48000)
        self.assertEqual(rep.mediaDuration, 288768)
        self.assertEqual(rep.encrypted, False)
        self.assertEqual(rep.lang, "und")
        self.assertEqual(rep.numChannels, 6)
        self.assertEqual(rep.sampleRate, 48000)


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            RepresentationTests)

if __name__ == "__main__":
    unittest.main()
