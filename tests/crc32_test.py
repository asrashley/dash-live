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
import base64
import os
import sys
import unittest

_src = os.path.join(os.path.dirname(__file__), "..", "src")
if _src not in sys.path:
    sys.path.append(_src)

from mixins.testcase import TestCaseMixin
from purecrc import Crc32Mpeg2

class Crc32Tests(TestCaseMixin, unittest.TestCase):
    def test_pure_python_crc32(self):
        crc = Crc32Mpeg2()
        data = map(lambda b: ord(b), b'Hi!')
        crc.process(data)
        result = crc.final()
        self.assertEqual(result, 0x6ADC4B4B)

    def test_mpeg_table_section_equals_zero(self):
        data = base64.b64decode(
            r'/DAvAAAAAAAA///wFAVIAACPf+/+c2nALv4AUsz1AAAAAAAKAAhDVUVJAAABNWLbowo=')
        crc = Crc32Mpeg2()
        crc.process(map(lambda b: ord(b), data))
        self.assertEqual(crc.final(), 0)

        crc = Crc32Mpeg2()
        crc.process(map(lambda b: ord(b), data[:-4]))
        self.assertEqual(crc.final(), 0x62dba30a)


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            Crc32Tests)

if __name__ == "__main__":
    unittest.main()
