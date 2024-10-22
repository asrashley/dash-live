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
from pathlib import Path
import unittest
from typing import ClassVar

from dashlive.mpeg.dash.representation import Representation
from dashlive.mpeg.dash.segment import Segment
from dashlive.mpeg import mp4
from dashlive.utils.buffered_reader import BufferedReader

class SegmentTests(unittest.TestCase):
    FIXTURES_PATH: ClassVar[Path] = Path(__file__).parent / "fixtures" / "bbb"

    def test_index_media(self):
        for name in ["bbb_a1.mp4", "bbb_a1_enc.mp4", "bbb_a2.mp4", "bbb_v6.mp4",
                     "bbb_v6_enc.mp4", "bbb_v7.mp4", "bbb_v7_enc.mp4", ]:
            filename = SegmentTests.FIXTURES_PATH / name
            with filename.open('rb') as src:
                wrap = mp4.Wrapper(
                    atom_type='wrap', parent=None,
                    children=mp4.Mp4Atom.load(BufferedReader(src)))
            rep = Representation.load(filename=name, atoms=wrap.children)
            self.assertEqual(rep.version, Representation.VERSION)
            if 'v' in name:
                self.assertEqual(rep.content_type, "video")
                self.assertEqual(rep.timescale, 240)
            else:
                self.assertEqual(rep.content_type, "audio")
                self.assertEqual(rep.timescale, 44100)
                self.assertEqual(rep.sampleRate, 44100)
            if 'enc' in name:
                self.assertTrue(rep.encrypted)
            self.assertEqual(rep.segments[0].pos, 0)
            idx = 0
            pos = 0
            for c in wrap.children:
                if c.atom_type == 'moof':
                    msg = 'Expected position for segment {:d} of {:s} to be {:d} but was {:d}'.format(
                        idx, name, rep.segments[idx].pos, pos)
                    self.assertEqual(rep.segments[idx].pos, pos, msg)
                    msg = 'Expected size for segment {:d} of {:s} to be {:d} but was {:d}'.format(
                        idx, name, c.position - pos, rep.segments[idx].size)
                    self.assertEqual(
                        c.position - pos, rep.segments[idx].size, msg)
                    pos = c.position
                    idx += 1

    def test_string_output(self) -> None:
        seg = Segment(pos=0, size=123, duration=3600)
        self.assertEqual(str(seg), '(0,123,3600)')
        seg = Segment(pos=0, size=123)
        self.assertEqual(str(seg), '(0,123)')


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            SegmentTests)

if __name__ == "__main__":
    unittest.main()
