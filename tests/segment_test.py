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
import logging
import os
import sys
import unittest

_src = os.path.join(os.path.dirname(__file__), "..", "src")
if _src not in sys.path:
    sys.path.append(_src)

from mpeg.dash.representation import Representation
from mpeg import mp4
from utils.buffered_reader import BufferedReader

class SegmentTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = os.path.join(os.path.dirname(__file__), "fixtures")
        logging.basicConfig(level=logging.WARNING)

    def test_index_media(self):
        for name in ["bbb_a1.mp4", "bbb_a1_enc.mp4", "bbb_a2.mp4", "bbb_v6.mp4",
                     "bbb_v6_enc.mp4", "bbb_v7.mp4", "bbb_v7_enc.mp4", ]:
            filename = os.path.join(self.fixtures, name)
            src = BufferedReader(io.FileIO(filename, 'rb'))
            wrap = mp4.Wrapper(atom_type='wrap', parent=None,
                               children=mp4.Mp4Atom.load(src))
            rep = Representation.load(filename=name, atoms=wrap.children)
            self.assertEqual(rep.version, Representation.VERSION)
            if 'v' in name:
                self.assertEqual(rep.contentType, "video")
                self.assertEqual(rep.timescale, 240)
            else:
                self.assertEqual(rep.contentType, "audio")
                self.assertEqual(rep.timescale, 44100)
                self.assertEqual(rep.sampleRate, 44100)
            if 'enc' in name:
                self.assertTrue(rep.encrypted)
            self.assertEqual(rep.segments[0].pos, 0)
            idx = 0
            pos = 0
            for c in wrap.children:
                if c.atom_type == 'moof':
                    msg = 'Expected position for segment {0:d} of {1:s} to be {2:d} but was {3:d}'.format(
                        idx, name, rep.segments[idx].pos, pos)
                    self.assertEqual(rep.segments[idx].pos, pos, msg)
                    msg = 'Expected size for segment {0:d} of {1:s} to be {2:d} but was {3:d}'.format(
                        idx, name, c.position - pos, rep.segments[idx].size)
                    self.assertEqual(
                        c.position - pos, rep.segments[idx].size, msg)
                    pos = c.position
                    idx += 1


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            SegmentTests)

if __name__ == "__main__":
    unittest.main()
