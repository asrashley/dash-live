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
from binascii import a2b_hex
import logging
import os
import sys
import unittest

from dashlive.drm.keymaterial import KeyMaterial
from dashlive.testcase.mixin import TestCaseMixin

class KeyMaterialTests(TestCaseMixin, unittest.TestCase):
    def test_base64_input(self):
        value = a2b_hex('0123456789abcdef0123456789abcdef')
        b64_value = base64.b64encode(value)
        km = KeyMaterial(value=b64_value)
        self.assertEqual(km.raw, value)
        km = KeyMaterial(b64=b64_value)
        self.assertEqual(km.raw, value)
        km.b64 = b64_value
        self.assertEqual(km.raw, value)
        self.assertEqual(len(km), 16)

    def test_raw_input(self):
        value = a2b_hex('0123456789abcdef0123456789abcdef')
        km = KeyMaterial(value=value)
        self.assertEqual(km.raw, value)
        km = KeyMaterial(raw=value)
        self.assertEqual(km.raw, value)
        with self.assertRaises(ValueError):
            km = KeyMaterial(raw=value[3:])

    def test_hex_input(self):
        value = '0123456789abcdef0123456789abcdef'
        km = KeyMaterial(value=value)
        self.assertEqual(km.raw, a2b_hex(value))
        km = KeyMaterial(value=('0x' + value))
        self.assertEqual(km.raw, a2b_hex(value))
        km = KeyMaterial(hex=value)
        self.assertEqual(km.raw, a2b_hex(value))
        dash_value = '01234567-89ab-cdef-0123-456789abcdef'
        km = KeyMaterial(value=dash_value)
        self.assertEqual(km.raw, a2b_hex(value))
        km = KeyMaterial(hex=dash_value)
        self.assertEqual(km.raw, a2b_hex(value))
        km.hex = dash_value
        self.assertEqual(km.raw, a2b_hex(value))

    def test_no_input(self):
        with self.assertRaises(ValueError):
            _ = KeyMaterial()

    def test_output(self):
        value = '0123456789abcdef0123456789abcdef'
        km = KeyMaterial(value=value)
        self.assertEqual(km.raw, a2b_hex(value))
        self.assertEqual(km.to_hex(), value)
        self.assertEqual(km.hex, value)
        b64_value = self.to_base64(a2b_hex(value))
        self.assertEqual(km.to_base64(), b64_value)
        self.assertEqual(km.b64, b64_value)


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        FORMAT = r"%(asctime)-15s:%(levelname)s:%(filename)s@%(lineno)d: %(message)s"
        logging.basicConfig(format=FORMAT, level=logging.DEBUG)
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            KeyMaterialTests)

if __name__ == "__main__":
    unittest.main()
