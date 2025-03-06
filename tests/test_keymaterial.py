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
import binascii
import unittest

from dashlive.drm.keymaterial import KeyMaterial

from .mixins.mixin import TestCaseMixin

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

    def test_guid_generation(self) -> None:
        default_kid = '1AB45440-532C-4399-94DC-5C5AD9584BAC'.lower()
        expected_uuid = '4054b41a-2c53-9943-94dc-5c5ad9584bac'
        km = KeyMaterial(hex=default_kid)
        guid = km.hex_to_le_guid(raw=False)
        self.assertEqual(expected_uuid, guid)
        raw_kid = binascii.a2b_hex(guid.replace('-', ''))
        self.assertEqual(len(raw_kid), 16)
        hex_uuid = expected_uuid.replace('-', '')
        raw_uuid = binascii.a2b_hex(hex_uuid)
        self.assertEqual(len(raw_uuid), 16)
        for i in range(len(raw_kid)):
            self.assertEqual(
                raw_kid[i], raw_uuid[i],
                f'Expected 0x{raw_kid[i]:02x} got 0x{raw_uuid[i]:02x} at {i}')
        self.assertEqual(
            expected_uuid.replace('-', ''),
            self.to_hex(raw_kid))
        self.assertEqual(
            binascii.a2b_hex(expected_uuid.replace('-', '')),
            raw_kid)
        base64_kid = self.to_base64(raw_kid)
        self.assertEqual(r'QFS0GixTmUOU3Fxa2VhLrA==', base64_kid)
        with self.assertRaises(ValueError):
            km = KeyMaterial(raw=b'invalid')
            KeyMaterial.hex_to_le_guid(raw=True)
        with self.assertRaises(ValueError):
            km = KeyMaterial(hex='ab012345')
            KeyMaterial.hex_to_le_guid(raw=False)


if __name__ == "__main__":
    unittest.main()
