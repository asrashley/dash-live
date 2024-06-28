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

from dashlive.mpeg.codec_strings import H264Codec, H265Codec, Mp4AudioCodec

from .mixins.flask_base import FlaskTestBase

class CodecStringTests(FlaskTestBase, unittest.TestCase):
    def test_avc(self) -> None:
        test_cases = [
            ("avc1.64002A", 100, 4.2),
            ("avc1.640020", 100, 3.2),
            ("avc1.64001F", 100, 3.1),
            ("avc1.64001E", 100, 3),
            ("avc1.640015", 100, 2.1),
            ("avc1.640014", 100, 2),
            ("avc1.4D4014", 77, 2),
        ]
        for tc, profile, level in test_cases:
            codec_data = H264Codec.from_string(tc)
            self.assertEqual(profile, codec_data.profile)
            self.assertEqual(level, codec_data.level)
            self.assertEqual(tc, codec_data.to_string())

    def test_hev1(self) -> None:
        test_cases = [
            'hev1.2.4.L153.B0', 'hvc1.2.4.L153.B0',
            'hev1.2.4.L93.90']
        for tc in test_cases:
            codec_data = H265Codec.from_string(tc)
            self.assertEqual(tc, codec_data.to_string())

    def test_aac(self) -> None:
        test_cases = [
            ("mp4a.40.2", 0x40, 2, "MPEG-4 AAC LC"),
            ("mp4a.40.02", 0x40, 2, "MPEG-4 AAC LC"),
            ("mp4a.40.5", 0x40, 5, "MPEG-4 AAC SBR"),
            ("mp4a.40.05", 0x40, 5, "MPEG-4 AAC SBR"),
            ("mp4a.40.29", 0x40, 29, "MPEG-4 AAC LC + SBR + PS"),
            ("mp4a.67", 0x67, 0, "MPEG-2 AAC LC"),
        ]
        for tc, object_type, audio_object_type, profile in test_cases:
            codec_data = Mp4AudioCodec.from_string(tc)
            self.assertEqual(codec_data.object_type, object_type)
            self.assertEqual(codec_data.audio_object_type, audio_object_type)
            self.assertEqual(codec_data.profile_string(), profile)


if __name__ == "__main__":
    unittest.main()
