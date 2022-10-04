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

import logging
import os
import sys
import unittest

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src not in sys.path:
    sys.path.append(_src)

from drm.clearkey import ClearKey
from mpeg.dash.representation import Representation
from templates.factory import TemplateFactory
from testcase.mixin import TestCaseMixin
from key_stub import KeyStub

class ClearkeyTests(TestCaseMixin, unittest.TestCase):
    def setUp(self):
        self.templates = TemplateFactory()
        self.keys = {
            "0123456789012345".encode('hex'): "ccc0f2b3b279926496a7f5d25da692f6",
            "ABCDEFGHIJKLMNOP".encode('hex'): "ccc0f2b3b279926496a7f5d25da692f6",
        }
        for kid in self.keys.keys():
            self.keys[kid] = KeyStub(kid, self.keys[kid])
        self.la_url = 'http://localhost:9080/clearkey'

    def test_pssh_generation(self):
        expected_pssh = [
            0x00, 0x00, 0x00, 0x44, 0x70, 0x73, 0x73, 0x68,
            0x01, 0x00, 0x00, 0x00,
            0x10, 0x77, 0xef, 0xec, 0xc0, 0xb2, 0x4d, 0x02,
            0xac, 0xe3, 0x3c, 0x1e, 0x52, 0xe2, 0xfb, 0x4b,
            0x00, 0x00, 0x00, 0x02,
            0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37,
            0x38, 0x39, 0x30, 0x31, 0x32, 0x33, 0x34, 0x35,
            0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48,
            0x49, 0x4a, 0x4b, 0x4c, 0x4d, 0x4e, 0x4f, 0x50,
            0x00, 0x00, 0x00, 0x00,
        ]
        expected_pssh = ''.join(map(lambda a: chr(a), expected_pssh))
        ck = ClearKey(self.templates)
        representation = Representation(
            id='V1', default_kid=self.keys.keys()[0])
        keys = sorted(self.keys.keys())
        pssh = ck.generate_pssh(representation, keys).encode()
        self.assertBuffersEqual(expected_pssh, pssh)


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        FORMAT = r"%(asctime)-15s:%(levelname)s:%(filename)s@%(lineno)d: %(message)s"
        logging.basicConfig(format=FORMAT, level=logging.DEBUG)
        # mp4_log = logging.getLogger('mp4')
        # mp4_log.setLevel(logging.DEBUG)
        # fio_log = logging.getLogger('fio')
        # fio_log.setLevel(logging.DEBUG)
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            ClearkeyTests)

if __name__ == "__main__":
    unittest.main()