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

from dashlive.server import models
from dashlive.mpeg.mp4 import Mp4Atom
from dashlive.mpeg.dash.representation import Representation
from dashlive.utils.buffered_reader import BufferedReader

from .mixins.flask_base import FlaskTestBase

class RepresentationTests(FlaskTestBase, unittest.TestCase):
    def test_load_representation(self) -> None:
        self.setup_media(with_subs=True)
        self.assertGreaterThan(models.MediaFile.count(), 0)
        for mfile in models.MediaFile.all():
            filename = self.FIXTURES_PATH / f'{mfile.name}.mp4'
            with filename.open('rb') as src:
                atoms = Mp4Atom.load(BufferedReader(src))
            rep = Representation.load(filename, atoms)
            expected = rep.toJSON()
            actual = mfile.representation.toJSON()
            self.assertObjectEqual(expected, actual)

    def test_load_ebu_tt_d(self):
        filename = self.FIXTURES_PATH / "ebuttd.mp4"
        with filename.open('rb') as src:
            atoms = Mp4Atom.load(BufferedReader(src))
        rep = Representation.load(filename, atoms)
        self.assertEqual(rep.content_type, 'text')
        self.assertEqual(rep.timescale, 200)
        self.assertEqual(rep.mimeType, 'application/ttml+xml')
        self.assertEqual(rep.codecs, 'im1t|etd1')

    def test_load_bbb_t1(self):
        filename = self.FIXTURES_PATH / "bbb_t1.mp4"
        with filename.open('rb') as src:
            atoms = Mp4Atom.load(BufferedReader(src))
        rep = Representation.load(filename, atoms)
        self.assertEqual(rep.content_type, 'text')
        self.assertEqual(rep.timescale, 200)
        self.assertEqual(rep.mimeType, 'application/mp4')
        self.assertEqual(rep.codecs, 'stpp')

    def test_load_web_vtt(self):
        filename = self.FIXTURES_PATH / "webvtt.mp4"
        with filename.open('rb') as src:
            atoms = Mp4Atom.load(BufferedReader(src))
        rep = Representation.load(filename, atoms)
        self.assertEqual(rep.content_type, 'text')
        self.assertEqual(rep.timescale, 1000)
        self.assertEqual(rep.mimeType, 'text/vtt')
        self.assertEqual(rep.codecs, 'wvtt')
        self.assertEqual(rep.mediaDuration, 39868)
        self.assertEqual(rep.encrypted, False)
        # 1 init segment + 3 media segments
        self.assertEqual(len(rep.segments), 4)

    def test_load_hevc(self):
        filename = self.FIXTURES_PATH / "hevc-rep.mp4"
        with filename.open('rb') as src:
            atoms = Mp4Atom.load(BufferedReader(src))
        rep = Representation.load(filename, atoms)
        self.assertEqual(rep.content_type, 'video')
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
        filename = self.FIXTURES_PATH / "ac3-rep.mp4"
        with filename.open('rb') as src:
            atoms = Mp4Atom.load(BufferedReader(src))
        rep = Representation.load(filename, atoms)
        self.assertEqual(rep.content_type, 'audio')
        self.assertEqual(rep.timescale, 48000)
        self.assertEqual(rep.mimeType, 'audio/mp4')
        self.assertEqual(rep.codecs, 'ac-3')
        self.assertEqual(rep.segment_duration, 2 * 48000)
        self.assertEqual(rep.mediaDuration, 288768)
        self.assertEqual(rep.encrypted, False)
        self.assertEqual(rep.lang, "und")
        self.assertEqual(rep.numChannels, 6)
        self.assertEqual(rep.sampleRate, 48000)

    def test_load_eac3(self):
        filename = self.FIXTURES_PATH / "bbb_a2.mp4"
        with filename.open('rb') as src:
            atoms = Mp4Atom.load(BufferedReader(src))
        rep = Representation.load(filename, atoms)
        self.assertEqual(rep.content_type, 'audio')
        self.assertEqual(rep.timescale, 44100)
        self.assertEqual(rep.mimeType, 'audio/mp4')
        self.assertEqual(rep.codecs, 'ec-3')
        self.assertEqual(rep.segment_duration, 176298)
        self.assertEqual(rep.mediaDuration, 1763328)
        self.assertEqual(rep.encrypted, False)
        self.assertEqual(rep.lang, "und")
        self.assertEqual(rep.numChannels, 6)
        self.assertEqual(rep.sampleRate, 44100)

    def test_load_encrypted_eac3(self):
        filename = self.FIXTURES_PATH / "bbb_a2_enc.mp4"
        with filename.open('rb') as src:
            atoms = Mp4Atom.load(BufferedReader(src))
        rep = Representation.load(filename, atoms)
        self.assertEqual(rep.content_type, 'audio')
        self.assertEqual(rep.timescale, 44100)
        self.assertEqual(rep.mimeType, 'audio/mp4')
        self.assertEqual(rep.codecs, 'ec-3')
        self.assertEqual(rep.segment_duration, 176298)
        self.assertEqual(rep.mediaDuration, 1763328)
        self.assertEqual(rep.encrypted, True)
        self.assertEqual(rep.lang, "und")
        self.assertEqual(rep.numChannels, 6)
        self.assertEqual(rep.sampleRate, 44100)


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            RepresentationTests)

if __name__ == "__main__":
    unittest.main()
