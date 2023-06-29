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
import binascii
import logging
import os
import unittest

from dashlive.drm.marlin import Marlin
from dashlive.mpeg.dash.representation import Representation
from dashlive.testcase.mixin import TestCaseMixin

from .key_stub import KeyStub

def to_hex(data: bytes) -> str:
    return str(binascii.b2a_hex(data), 'ascii')

class MarlinTests(TestCaseMixin, unittest.TestCase):
    def test_pssh_generation_raises_an_exception(self):
        mar = Marlin()
        keys = {
            to_hex(b'0123456789012345'): "ccc0f2b3b279926496a7f5d25da692f6",
            to_hex(b'ABCDEFGHIJKLMNOP'): "ccc0f2b3b279926496a7f5d25da692f6",
        }
        for kid in list(keys.keys()):
            keys[kid] = KeyStub(kid, keys[kid])
        representation = Representation(
            id='V1', default_kid=list(keys.keys())[0])
        keys = sorted(keys.keys())
        with self.assertRaises(RuntimeError):
            _ = mar.generate_pssh(representation, keys)

    def test_is_supported(self):
        test_cases = [
            ("urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed", False),
            ("urn:uuid:5e629af5-38da-4063-8977-97ffbd9902d4", True),
            ("urn:uuid:9a04f079-9840-4286-ab92-e65be0885f95", False),
            ("bad string", False),
            ("", False),
        ]
        for text, expected in test_cases:
            self.assertEqual(Marlin.is_supported_scheme_id(text), expected)
            self.assertEqual(Marlin.is_supported_scheme_id(text.upper()), expected)

    def test_dash_scheme_id(self):
        mar = Marlin()
        self.assertEqual(
            mar.dash_scheme_id(),
            "urn:uuid:5e629af5-38da-4063-8977-97ffbd9902d4")


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        FORMAT = r"%(asctime)-15s:%(levelname)s:%(filename)s@%(lineno)d: %(message)s"
        logging.basicConfig(format=FORMAT, level=logging.DEBUG)
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            MarlinTests)

if __name__ == "__main__":
    unittest.main()
