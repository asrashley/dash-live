############################################################################
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
import binascii
from concurrent.futures import ThreadPoolExecutor
import io
import logging
import os
from typing import Any
import unittest
import urllib.request
import urllib.parse
import urllib.error

import flask
from lxml import etree

from dashlive.drm.keymaterial import KeyMaterial
from dashlive.drm.playready import PlayReady
from dashlive.mpeg import mp4
from dashlive.mpeg.dash.validator import ConcurrentWorkerPool
from dashlive.server import manifests, models
from dashlive.utils.binary import Binary
from dashlive.utils.buffered_reader import BufferedReader

from .mixins.flask_base import FlaskTestBase
from .key_stub import KeyStub
from .mixins.check_manifest import DashManifestCheckMixin
from .mixins.view_validator import ViewsTestDashValidator

class PlayreadyTests(FlaskTestBase, DashManifestCheckMixin):
    custom_attributes = [dict(tag='IIS_DRM_VERSION', value='8.0.1907.32')]

    expected_pro = ''.join([
        r'VAMAAAEAAQBKAzwAVwBSAE0ASABFAEEARABFAFIAIAB4AG0AbABuAHMAPQAi',
        r'AGgAdAB0AHAAOgAvAC8AcwBjAGgAZQBtAGEAcwAuAG0AaQBjAHIAbwBzAG8A',
        r'ZgB0AC4AYwBvAG0ALwBEAFIATQAvADIAMAAwADcALwAwADMALwBQAGwAYQB5',
        r'AFIAZQBhAGQAeQBIAGUAYQBkAGUAcgAiACAAdgBlAHIAcwBpAG8AbgA9ACIA',
        r'NAAuADAALgAwAC4AMAAiAD4APABEAEEAVABBAD4APABQAFIATwBUAEUAQwBU',
        r'AEkATgBGAE8APgA8AEsARQBZAEwARQBOAD4AMQA2ADwALwBLAEUAWQBMAEUA',
        r'TgA+ADwAQQBMAEcASQBEAD4AQQBFAFMAQwBUAFIAPAAvAEEATABHAEkARAA+',
        r'ADwALwBQAFIATwBUAEUAQwBUAEkATgBGAE8APgA8AEsASQBEAD4AUQBGAFMA',
        r'MABHAGkAeABUAG0AVQBPAFUAMwBGAHgAYQAyAFYAaABMAHIAQQA9AD0APAAv',
        r'AEsASQBEAD4APABDAEgARQBDAEsAUwBVAE0APgBYAHkANgBqAEsARwA0AFAA',
        r'SgBTAFkAPQA8AC8AQwBIAEUAQwBLAFMAVQBNAD4APABMAEEAXwBVAFIATAA+',
        r'AGgAdAB0AHAAcwA6AC8ALwBhAG0AcwBzAGEAbQBwAGwAZQBzAC4AawBlAHkA',
        r'ZABlAGwAaQB2AGUAcgB5AC4AbQBlAGQAaQBhAHMAZQByAHYAaQBjAGUAcwAu',
        r'AHcAaQBuAGQAbwB3AHMALgBuAGUAdAAvAFAAbABhAHkAUgBlAGEAZAB5AC8A',
        r'PAAvAEwAQQBfAFUAUgBMAD4APABDAFUAUwBUAE8ATQBBAFQAVABSAEkAQgBV',
        r'AFQARQBTAD4APABJAEkAUwBfAEQAUgBNAF8AVgBFAFIAUwBJAE8ATgA+ADgA',
        r'LgAwAC4AMQA5ADAANwAuADMAMgA8AC8ASQBJAFMAXwBEAFIATQBfAFYARQBS',
        r'AFMASQBPAE4APgA8AC8AQwBVAFMAVABPAE0AQQBUAFQAUgBJAEIAVQBUAEUA',
        r'UwA+ADwALwBEAEEAVABBAD4APAAvAFcAUgBNAEgARQBBAEQARQBSAD4A'])

    la_url = 'https://amssamples.keydelivery.mediaservices.windows.net/PlayReady/'

    namespaces = {
        'prh': 'http://schemas.microsoft.com/DRM/2007/03/PlayReadyHeader',
    }

    def setUp(self):
        super().setUp()
        self.keys = {}
        for kid, key in [
                ("1AB45440532C439994DC5C5AD9584BAC", "ccc0f2b3b279926496a7f5d25da692f6")]:
            self.keys[kid.lower()] = KeyStub(kid, key)
        self.default_kid: str = list(self.keys.keys())[0]

    def test_guid_generation(self):
        default_kid = '1AB45440-532C-4399-94DC-5C5AD9584BAC'.lower()
        expected_uuid = '4054b41a-2c53-9943-94dc-5c5ad9584bac'
        mspr = PlayReady(la_url=self.la_url)
        guid = mspr.hex_to_le_guid(default_kid, raw=False)
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
            PlayReady.hex_to_le_guid(guid=b'invalid', raw=True)
        with self.assertRaises(ValueError):
            PlayReady.hex_to_le_guid(guid='ab012345', raw=False)

    def test_content_key_generation(self):
        # https://brokenpipe.wordpress.com/2016/10/06/generating-a-playready-content-key-using-a-key-seed-and-key-id/
        kid = binascii.a2b_hex(
            '01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-', ''))
        expected_key = base64.b64decode('GUf166PQbx+sgBADjyBMvw==')
        key = PlayReady.generate_content_key(kid)
        self.assertEqual(self.to_hex(key), self.to_hex(expected_key))

        # Unified streaming example
        # kid='c001de8e567b5fcfbc22c565ed5bda24'.decode('hex')
        # expected_key='533a583a843436a536fbe2a5821c4b6c'.decode('hex')
        # mspr = PlayReady(la_url=self.la_url)
        # key = mspr.generate_content_key(kid)
        # self.assertEqual(binascii.b2a_hex(key), binascii.b2a_hex(expected_key))

        # http://profficialsite.origin.mediaservices.windows.net/228e2071-c79b-4bb7-b999-0f74801c924a/tearsofsteel_1080p_60s_24fps.6000kbps.1920x1080.h264-8b.2ch.128kbps.aac.avsep.cenc.mp4
        KID = binascii.a2b_hex('a2c786d0f9ef4cb3b333cd323a4284a5')
        CEK = binascii.a2b_hex('4edb7704cdbf03617f4800bd878a6df2')
        key = PlayReady.generate_content_key(KID)
        self.assertEqual(binascii.b2a_hex(key), binascii.b2a_hex(CEK))
        with self.assertRaises(ValueError):
            PlayReady.generate_content_key(keyId=b'123')
        with self.assertRaises(ValueError):
            PlayReady.generate_content_key(keyId=kid, keySeed=b'123')

    def test_checksum_generation(self):
        mspr = PlayReady(la_url=self.la_url)
        kid_hex = '01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-', '')
        key_hex = self.to_hex(base64.b64decode('GUf166PQbx+sgBADjyBMvw=='))
        expected_checksum = base64.b64decode(r'EV/EKanLDy4=')
        keypair = KeyStub(kid_hex, key_hex)
        checksum = mspr.generate_checksum(keypair)
        self.assertEqual(
            self.to_hex(checksum),
            self.to_hex(expected_checksum))

    def test_wrm_generation(self):
        expected_wrm = ''.join([
            r'<WRMHEADER xmlns="http://schemas.microsoft.com/DRM/2007/03/PlayReadyHeader" version="4.0.0.0">',
            r'<DATA><PROTECTINFO><KEYLEN>16</KEYLEN><ALGID>AESCTR</ALGID></PROTECTINFO>',
            r'<KID>QFS0GixTmUOU3Fxa2VhLrA==</KID><CHECKSUM>Xy6jKG4PJSY=</CHECKSUM>',
            r'<LA_URL>https://amssamples.keydelivery.mediaservices.windows.net/PlayReady/</LA_URL>',
            r'</DATA></WRMHEADER>'])
        expected_wrm = expected_wrm.encode('utf-16')
        self.maxDiff = None
        mspr = PlayReady(
            la_url=self.la_url,
            version=2.0,
            header_version=4.0)
        mspr.generate_checksum = lambda keypair: binascii.a2b_base64(
            'Xy6jKG4PJSY=')
        wrm = mspr.generate_wrmheader(self.la_url, self.default_kid, self.keys, None)
        self.assertEqual(expected_wrm.decode('utf-16'), wrm.decode('utf-16'))
        if expected_wrm[0] == 0xFF and expected_wrm[1] == 0xFE:
            # remove UTF-16 byte order mark
            expected_wrm = expected_wrm[2:]
        self.assertBuffersEqual(expected_wrm, wrm, name="WRMHEADER")

    def test_wrm_generation_with_custom_attrs(self):
        expected_wrm = ''.join([
            r'<WRMHEADER xmlns="http://schemas.microsoft.com/DRM/2007/03/PlayReadyHeader" version="4.0.0.0">',
            r'<DATA><PROTECTINFO><KEYLEN>16</KEYLEN><ALGID>AESCTR</ALGID></PROTECTINFO>',
            r'<KID>QFS0GixTmUOU3Fxa2VhLrA==</KID><CHECKSUM>Xy6jKG4PJSY=</CHECKSUM>',
            r'<LA_URL>https://amssamples.keydelivery.mediaservices.windows.net/PlayReady/</LA_URL>',
            r'<CUSTOMATTRIBUTES><IIS_DRM_VERSION>8.0.1907.32</IIS_DRM_VERSION>',
            r'</CUSTOMATTRIBUTES></DATA></WRMHEADER>'])
        expected_wrm = expected_wrm.encode('utf-16')
        self.maxDiff = None
        mspr = PlayReady(
            la_url=self.la_url,
            version=2.0,
            header_version=4.0)
        mspr.generate_checksum = lambda keypair: binascii.a2b_base64(
            'Xy6jKG4PJSY=')
        wrm = mspr.generate_wrmheader(
            self.la_url, self.default_kid, self.keys, self.custom_attributes)
        self.assertEqual(expected_wrm.decode('utf-16'), wrm.decode('utf-16'))
        if expected_wrm[0] == 0xFF and expected_wrm[1] == 0xFE:
            # remove UTF-16 byte order mark
            expected_wrm = expected_wrm[2:]
        self.assertEqual(expected_wrm, wrm)

    def test_wrm_generation_with_sorted_custom_attrs(self):
        expected_wrm = ''.join([
            r'<WRMHEADER xmlns="http://schemas.microsoft.com/DRM/2007/03/PlayReadyHeader" version="4.0.0.0">',
            r'<DATA><PROTECTINFO><KEYLEN>16</KEYLEN><ALGID>AESCTR</ALGID></PROTECTINFO>',
            r'<KID>QFS0GixTmUOU3Fxa2VhLrA==</KID><CHECKSUM>Xy6jKG4PJSY=</CHECKSUM>',
            r'<LA_URL>https://amssamples.keydelivery.mediaservices.windows.net/PlayReady/</LA_URL>',
            r'<CUSTOMATTRIBUTES><MyNode BarAttribute="Bar" FooAttribute="Foo"></MyNode></CUSTOMATTRIBUTES>',
            r'</DATA></WRMHEADER>'])
        expected_wrm = expected_wrm.encode('utf-16')
        self.maxDiff = None
        mspr = PlayReady(
            la_url=self.la_url,
            version=2.0,
            header_version=4.0)
        mspr.generate_checksum = lambda keypair: binascii.a2b_base64(
            'Xy6jKG4PJSY=')
        custom_attributes = [
            dict(tag='MyNode', value='', attributes=dict(FooAttribute="Foo", BarAttribute="Bar"))
        ]
        wrm = mspr.generate_wrmheader(
            self.la_url, self.default_kid, self.keys, custom_attributes)
        self.assertEqual(expected_wrm.decode('utf-16'), wrm.decode('utf-16'))
        if expected_wrm[0] == 0xFF and expected_wrm[1] == 0xFE:
            # remove UTF-16 byte order mark
            expected_wrm = expected_wrm[2:]
        self.assertEqual(expected_wrm, wrm)

    def test_pro_generation(self):
        self.maxDiff = None
        mspr = PlayReady(
            la_url=self.la_url,
            version=2.0,
            header_version=4.0)
        mspr.generate_checksum = lambda keypair: binascii.a2b_base64(
            'Xy6jKG4PJSY=')
        pro = mspr.generate_pro(
            self.la_url, self.default_kid, self.keys, self.custom_attributes)
        self.assertBuffersEqual(base64.b64decode(self.expected_pro), pro,
                                name="PlayReady Object")

    def test_parsing_pro_v4_0(self):
        """
        Check parsing of a pre-defined PlayReady Object (PRO)
        """
        mspr = PlayReady(
            la_url=self.la_url,
            header_version=4.0)
        mspr.generate_checksum = lambda keypair: binascii.a2b_base64(
            'Xy6jKG4PJSY=')
        e_pro = PlayReady.parse_pro(
            BufferedReader(
                None, data=base64.b64decode(
                    self.expected_pro)))
        xml = e_pro[0].xml
        self.assertEqual(xml.getroot().get("version"),
                         f'{mspr.header_version:02.1f}.0.0')
        algid = xml.findall(
            './prh:DATA/prh:PROTECTINFO/prh:ALGID',
            self.namespaces)
        self.assertEqual(len(algid), 1)
        self.assertEqual(algid[0].text, "AESCTR")
        keylen = xml.findall(
            './prh:DATA/prh:PROTECTINFO/prh:KEYLEN',
            self.namespaces)
        self.assertEqual(len(keylen), 1)
        self.assertEqual(keylen[0].text, "16")
        kid = xml.findall('./prh:DATA/prh:KID', self.namespaces)
        self.assertEqual(len(kid), 1)
        guid = PlayReady.hex_to_le_guid(list(self.keys.keys())[0], raw=False)
        self.assertEqual(
            self.to_hex(base64.b64decode(kid[0].text)),
            guid.replace('-', ''))

    def test_pssh_generation_v4_0(self):
        """Generate and parse PlayReady Header v4.0.0.0"""
        self.assertEqual(len(self.keys), 1)
        mspr = PlayReady(
            la_url=self.la_url,
            header_version=4.0)
        mspr.generate_checksum = lambda keypair: binascii.a2b_base64(
            'Xy6jKG4PJSY=')
        pssh = mspr.generate_pssh(
            self.la_url, self.default_kid, self.keys, self.custom_attributes).encode()
        self.check_generated_pssh_v4_0(self.keys, mspr, pssh)

    def check_generated_pssh_v4_0(self, keys, mspr, pssh):
        """
        Check the PSSH matches the v4.0.0.0 Schema
        """
        expected_len = 4 + 4  # Atom(length, 'pssh')
        expected_len += 4  # FullBox(version, flags)
        # PSSH(SystemID, DataSize, Data)
        expected_pro = base64.b64decode(self.expected_pro)
        expected_len += 16 + 4 + len(expected_pro)  # PSSH
        self.assertEqual(len(pssh), expected_len)
        parser = mp4.IsoParser()
        src = BufferedReader(None, data=pssh)
        atoms = parser.walk_atoms(src)
        self.assertEqual(len(atoms), 1)
        self.assertEqual(atoms[0].atom_type, 'pssh')
        self.assertEqual(atoms[0].version, 0)
        self.assertTrue(isinstance(atoms[0], mp4.ContentProtectionSpecificBox))
        self.assertEqual(len(atoms[0].key_ids), 0)
        self.assertIsInstance(atoms[0].system_id, Binary)
        self.assertEqual(atoms[0].system_id.data, PlayReady.RAW_SYSTEM_ID)
        self.assertEqual(
            self.to_hex(atoms[0].data.data),
            self.to_hex(expected_pro))
        actual_pro = mspr.parse_pro(
            BufferedReader(None, data=atoms[0].data.data))
        self.assertEqual(actual_pro[0].xml.getroot().get("version"),
                         '4.0.0.0')
        algid = actual_pro[0].xml.findall(
            './prh:DATA/prh:PROTECTINFO/prh:ALGID', self.namespaces)
        self.assertEqual(len(algid), 1)
        self.assertEqual(algid[0].text, "AESCTR")
        keylen = actual_pro[0].xml.findall(
            './prh:DATA/prh:PROTECTINFO/prh:KEYLEN', self.namespaces)
        self.assertEqual(len(keylen), 1)
        self.assertEqual(keylen[0].text, "16")
        kid = actual_pro[0].xml.findall(
            './prh:DATA/prh:KID', self.namespaces)
        self.assertEqual(len(kid), 1)
        guid = PlayReady.hex_to_le_guid(list(keys.keys())[0], raw=False)
        self.assertEqual(
            self.to_hex(base64.b64decode(kid[0].text)),
            guid.replace('-', ''))

    def test_pssh_generation_v4_1(self):
        """Generate and parse PlayReady Header v4.1.0.0"""
        self.assertEqual(len(self.keys), 1)
        mspr = PlayReady(
            la_url=self.la_url,
            header_version=4.1)
        mspr.generate_checksum = lambda keypair: binascii.a2b_base64(
            'Xy6jKG4PJSY=')
        pssh = mspr.generate_pssh(self.la_url, self.default_kid, self.keys).encode()
        self.check_generated_pssh_v4_1(self.keys, mspr, pssh)

    def check_generated_pssh_v4_1(self, keys, mspr, pssh):
        """
        Check the PSSH matches the v4.1.0.0 Schema
        """
        parser = mp4.IsoParser()
        src = BufferedReader(None, data=pssh)
        atoms = parser.walk_atoms(src)
        self.assertEqual(len(atoms), 1)
        self.assertEqual(atoms[0].atom_type, 'pssh')
        self.assertEqual(atoms[0].version, 0)
        self.assertTrue(isinstance(atoms[0], mp4.ContentProtectionSpecificBox))
        self.assertEqual(len(atoms[0].key_ids), 0)
        self.assertIsInstance(atoms[0].system_id, Binary)
        self.assertEqual(atoms[0].system_id.data, PlayReady.RAW_SYSTEM_ID)
        actual_pro = mspr.parse_pro(
            BufferedReader(None, data=atoms[0].data.data))
        self.assertEqual(
            actual_pro[0].xml.getroot().get("version"),
            '4.1.0.0')
        kid = actual_pro[0].xml.findall(
            './prh:DATA/prh:PROTECTINFO/prh:KID', self.namespaces)
        self.assertEqual(len(kid), 1)
        self.assertEqual(kid[0].get("ALGID"), "AESCTR")
        self.assertEqual(kid[0].get("CHECKSUM"), 'Xy6jKG4PJSY=')
        guid = PlayReady.hex_to_le_guid(list(keys.keys())[0], raw=False)
        self.assertEqual(
            self.to_hex(base64.b64decode(kid[0].get("VALUE"))),
            guid.replace('-', ''))

    def test_pssh_generation_v4_2(self):
        """Generate and parse PlayReady Header v4.2.0.0"""
        keys = {}
        for kid, key in [
                ("1AB45440532C439994DC5C5AD9584BAC",
                 "ccc0f2b3b279926496a7f5d25da692f6"),
                ("db06a8feec164de292282c71e9b856ab", "3179923adf3c929892951e62f93a518a")]:
            keys[kid.lower()] = KeyStub(kid, key)
        mspr = PlayReady(
            la_url=self.la_url,
            header_version=4.2)
        default_kid = list(keys.keys())[0]
        pssh = mspr.generate_pssh(self.la_url, default_kid, keys).encode()
        self.check_generated_pssh_v4_2(keys, mspr, pssh)

    def check_generated_pssh_v4_2(self, keys, mspr, pssh):
        """
        Check the PSSH matches the v4.2.0.0 Schema
        """
        parser = mp4.IsoParser()
        src = BufferedReader(None, data=pssh)
        atoms = parser.walk_atoms(src)
        self.assertEqual(len(atoms), 1)
        self.assertEqual(atoms[0].atom_type, 'pssh')
        self.assertTrue(isinstance(atoms[0], mp4.ContentProtectionSpecificBox))
        self.assertEqual(len(atoms[0].key_ids), len(keys))
        self.assertIsInstance(atoms[0].system_id, Binary)
        self.assertEqual(atoms[0].system_id.data, PlayReady.RAW_SYSTEM_ID)
        actual_pro = mspr.parse_pro(
            BufferedReader(
                None, data=atoms[0].data.data))
        self.assertEqual(
            actual_pro[0].xml.getroot().get("version"),
            '4.2.0.0')
        kids = actual_pro[0].xml.findall(
            './prh:DATA/prh:PROTECTINFO/prh:KIDS/prh:KID', self.namespaces)
        self.assertGreaterThan(len(keys), 0)
        guid_map = {}
        for keypair in list(keys.values()):
            guid = PlayReady.hex_to_le_guid(keypair.KID.raw, raw=True)
            guid = self.to_base64(guid)
            guid_map[guid] = keypair
        self.assertEqual(len(kids), len(keys))
        for kid in kids:
            self.assertEqual(kid.get("ALGID"), "AESCTR")
            if kid.get("VALUE") not in guid_map:
                print(guid_map.keys())
            keypair = guid_map[kid.get("VALUE")]
            checksum = mspr.generate_checksum(keypair)
            checksum = self.to_base64(checksum)
            self.assertEqual(kid.get("CHECKSUM"), checksum)

    def test_pssh_generation_v4_3(self):
        """
        Generate and parse PlayReady Header v4.3.0.0
        """
        self.keys = None
        keys = {}
        for kid, key in [
                ("1AB45440532C439994DC5C5AD9584BAC",
                 "ccc0f2b3b279926496a7f5d25da692f6"),
                ("db06a8feec164de292282c71e9b856ab", "3179923adf3c929892951e62f93a518a")]:
            keys[kid.lower()] = KeyStub(kid, key, alg='AESCBC')
        mspr = PlayReady(
            la_url=self.la_url,
            header_version=4.3)
        default_kid = list(keys.keys())[0]
        pssh = mspr.generate_pssh(self.la_url, default_kid, keys).encode()
        self.check_generated_pssh_v4_3(keys, mspr, pssh)

    def check_generated_pssh_v4_3(self, keys, mspr, pssh):
        """
        Check the PSSH matches the v4.3.0.0 Schema
        """
        parser = mp4.IsoParser()
        src = BufferedReader(None, data=pssh)
        atoms = parser.walk_atoms(src)
        self.assertEqual(len(atoms), 1)
        self.assertEqual(atoms[0].atom_type, 'pssh')
        self.assertTrue(isinstance(atoms[0], mp4.ContentProtectionSpecificBox))
        self.assertEqual(len(atoms[0].key_ids), len(keys))
        self.assertIsInstance(atoms[0].system_id, Binary)
        self.assertEqual(atoms[0].system_id.data, PlayReady.RAW_SYSTEM_ID)
        actual_pro = mspr.parse_pro(
            BufferedReader(
                None, data=atoms[0].data.data))
        self.assertEqual(
            actual_pro[0].xml.getroot().get("version"),
            '4.3.0.0')

        kids = actual_pro[0].xml.findall(
            './prh:DATA/prh:PROTECTINFO/prh:KIDS/prh:KID', self.namespaces)
        guid_map = {}
        for keypair in list(keys.values()):
            guid = PlayReady.hex_to_le_guid(keypair.KID.raw, raw=True)
            guid = self.to_base64(guid)
            guid_map[guid] = keypair
        self.assertEqual(len(kids), len(keys))
        for kid in kids:
            self.assertEqual(kid.get("ALGID"), "AESCBC")
            keypair = guid_map[kid.get("VALUE")]
            checksum = mspr.generate_checksum(keypair)
            checksum = self.to_base64(checksum)
            self.assertEqual(kid.get("CHECKSUM"), checksum)

    def test_pssh_generation_auto_header_version(self):
        """
        Generate and parse PlayReady object where header version automatically
        chosen
        """
        self.assertEqual(len(self.keys), 1)
        mspr = PlayReady(la_url=self.la_url, version=1.0)
        mspr.generate_checksum = lambda keypair: binascii.a2b_base64(
            'Xy6jKG4PJSY=')

        # check v4.0 (as defined in PlayReady v1.0)
        pssh = mspr.generate_pssh(
            self.la_url, self.default_kid, self.keys, self.custom_attributes).encode()
        self.check_generated_pssh_v4_0(self.keys, mspr, pssh)
        mspr.version = None
        pssh = mspr.generate_pssh(
            self.la_url, self.default_kid, self.keys, self.custom_attributes).encode()
        self.check_generated_pssh_v4_0(self.keys, mspr, pssh)

        # check v4.1 (as defined in PlayReady v2.0)
        mspr.version = 2.0
        pssh = mspr.generate_pssh(
            self.la_url, self.default_kid, self.keys).encode()
        self.check_generated_pssh_v4_1(self.keys, mspr, pssh)

        # check v4.2 (as defined in PlayReady v3.0)
        keys = {}
        for kid, key in [
                ("1AB45440532C439994DC5C5AD9584BAC", "ccc0f2b3b279926496a7f5d25da692f6"),
                ("db06a8feec164de292282c71e9b856ab", "3179923adf3c929892951e62f93a518a")]:
            keys[kid.lower()] = KeyStub(kid, key, alg='AESCTR')
        mspr.version = 3.0
        pssh = mspr.generate_pssh(
            self.la_url, "1AB45440532C439994DC5C5AD9584BAC", keys).encode()
        self.check_generated_pssh_v4_2(keys, mspr, pssh)
        mspr.version = None
        pssh = mspr.generate_pssh(
            self.la_url, "1AB45440532C439994DC5C5AD9584BAC", keys).encode()
        self.check_generated_pssh_v4_2(keys, mspr, pssh)

        # check v4.3 (as defined in PlayReady v4.0)
        keys = {}
        for kid, key in [
                ("1AB45440532C439994DC5C5AD9584BAC", "ccc0f2b3b279926496a7f5d25da692f6"),
                ("db06a8feec164de292282c71e9b856ab", "3179923adf3c929892951e62f93a518a")]:
            keys[kid.lower()] = KeyStub(kid, key, alg='AESCBC')
        mspr.version = 4.0
        pssh = mspr.generate_pssh(
            self.la_url, "1AB45440532C439994DC5C5AD9584BAC", keys).encode()
        self.check_generated_pssh_v4_3(keys, mspr, pssh)
        mspr.version = None
        pssh = mspr.generate_pssh(
            self.la_url, "1AB45440532C439994DC5C5AD9584BAC", keys).encode()
        self.check_generated_pssh_v4_3(keys, mspr, pssh)

    def test_insert_pssh(self):
        """
        Generate a PlayReady pssh box and insert it into an init segment
        """
        self.assertEqual(len(self.keys), 1)
        filename = self.FIXTURES_PATH / 'bbb_a1_enc.mp4'
        options = mp4.Options(mode='rw')
        with filename.open('rb') as f:
            with io.BufferedReader(f) as src:
                segments = mp4.Mp4Atom.load(src, options=options)
        init_seg = mp4.Wrapper(atom_type='wrap', options=options)
        for seg in segments:
            if seg.atom_type == 'moof':
                break
            init_seg.append_child(seg)
        # Expecting boxes: ftyp, free, free, moov, styp, sidx
        self.assertEqual(len(init_seg._children), 6)
        mspr = PlayReady(
            la_url=self.la_url,
            header_version=4.1)
        mspr.generate_checksum = lambda keypair: binascii.a2b_base64(
            'Xy6jKG4PJSY=')
        pssh = mspr.generate_pssh(
            self.la_url, self.default_kid, self.keys)
        self.check_generated_pssh_v4_1(self.keys, mspr, pssh.encode())
        before = len(init_seg.moov.children)
        init_seg.moov.append_child(pssh)
        self.assertEqual(len(init_seg.moov.children), before + 1)
        data = init_seg.encode()
        # with open('new_init_seg.mp4', 'wb') as tmp:
        #     tmp.write(data)
        src = BufferedReader(None, data=data)
        new_init_seg = mp4.Mp4Atom.load(src, options=options, use_wrapper=True)
        self.assertEqual(new_init_seg._children[0].atom_type, 'ftyp')
        self.assertEqual(len(new_init_seg.moov._children), len(init_seg.moov._children))
        expected = init_seg.toJSON()
        actual = new_init_seg.toJSON()
        self.maxDiff = None
        self.assertEqual(len(expected['children']), len(actual['children']))
        for atom in expected['children']:
            if atom['atom_type'] == 'pssh':
                atom['header_size'] = 8
        for exp, act in zip(expected['children'], actual['children']):
            self.assertObjectEqual(
                exp, act, msg=exp["atom_type"],
                list_key=self.list_key_fn)

    @staticmethod
    def list_key_fn(item: Any, index: int) -> str:
        if isinstance(item, dict):
            if '_type' in item:
                item_type = item["_type"].split('.')[-1]
                return f'{index}={item_type}'
            print(item.keys())
            return f'{index}={item["atom_type"]}'
        return f'{index}'

    async def test_playready_la_url(self):
        """
        PlayReady LA_URL in the manifest
        """
        # TODO: don't hard code KID
        test_la_url = PlayReady.TEST_LA_URL.format(
            cfgs='(kid:QFS0GixTmUOU3Fxa2VhLrA==,persist:false,sl:150)')
        await self.check_playready_la_url_value(test_la_url, [])

    async def test_playready_la_url_override(self):
        """
        Replace LA_URL in stream with CGI playready_la_url parameter
        """
        test_la_url = 'https://licence.url.override/'
        await self.check_playready_la_url_value(
            test_la_url,
            [f'playready_la_url={urllib.parse.quote_plus(test_la_url)}'])

    def test_is_supported_scheme_id(self):
        self.assertTrue(PlayReady.is_supported_scheme_id(
            "urn:uuid:9a04f079-9840-4286-ab92-e65be0885f95"))
        self.assertFalse(PlayReady.is_supported_scheme_id(
            "9a04f079-9840-4286-ab92-e65be0885f95"))
        self.assertTrue(PlayReady.is_supported_scheme_id(
            "urn:uuid:9a04f079-9840-4286-ab92-e65be0885f95".upper()))
        self.assertTrue(PlayReady.is_supported_scheme_id(
            "urn:uuid:79f0049a-4098-8642-ab92-e65be0885f95"))
        self.assertTrue(PlayReady.is_supported_scheme_id(
            "urn:uuid:79f0049a-4098-8642-ab92-e65be0885f95".upper()))
        self.assertFalse(PlayReady.is_supported_scheme_id(
            "79f0049a-4098-8642-ab92-e65be0885f95"))
        self.assertFalse(PlayReady.is_supported_scheme_id(
            "urn:uuid:5e629af5-38da-4063-8977-97ffbd9902d4"))

    async def check_playready_la_url_value(self, test_la_url: str,
                                           args: list[str]) -> None:
        """
        Check the LA_URL in the PRO element is correct
        """
        self.setup_media()
        self.logout_user()
        filename = 'hand_made.mpd'
        baseurl = flask.url_for(
            'dash-mpd-v3',
            manifest=filename,
            stream=self.FIXTURES_PATH.name,
            mode='vod')
        args += ['drm=playready']
        baseurl += '?' + '&'.join(args)
        response = self.client.get(baseurl)
        self.assertEqual(response.status_code, 200)
        xml = etree.parse(io.BytesIO(response.get_data(as_text=False)))
        with ThreadPoolExecutor(max_workers=4) as tpe:
            pool = ConcurrentWorkerPool(tpe)
            mpd = ViewsTestDashValidator(
                http_client=self.async_client, mode='vod', url=baseurl,
                encrypted=True, check_media=False,
                duration=self.SEGMENT_DURATION, pool=pool)
            await mpd.load(xml=xml.getroot())
            await mpd.validate()
        self.assertFalse(mpd.has_errors())
        self.assertEqual(len(mpd.manifest.periods), 1)
        schemeIdUri = "urn:uuid:" + PlayReady.SYSTEM_ID.lower()
        pro_tag = "{{{0}}}pro".format(mpd.xmlNamespaces['mspr'])
        for adap_set in mpd.manifest.periods[0].adaptation_sets:
            for prot in adap_set.contentProtection:
                if prot.schemeIdUri != schemeIdUri:
                    continue
                for elt in prot.children():
                    if elt.tag != pro_tag:
                        continue
                    pro = base64.b64decode(elt.text)
                    for record in PlayReady.parse_pro(
                            BufferedReader(None, data=pro)):
                        self.assertIsNotNone(record.xml)
                        la_urls = record.xml.findall(
                            './prh:DATA/prh:LA_URL', mpd.xmlNamespaces)
                        self.assertEqual(len(la_urls), 1)
                        self.assertEqual(la_urls[0].text, test_la_url)

    async def test_playready_v1_piff_sample_encryption(self):
        """
        PiffSampleEncryptionBox is inserted when using PlayReady v1.0
        """
        self.setup_media()
        self.logout_user()
        args = ['drm=playready', 'playready_version=1.0']
        await self.check_piff_uuid_is_present(args)

    async def test_playready_piff_sample_encryption_if_flag_present(self):
        """
        PiffSampleEncryptionBox is inserted when playready_piff=true option is used
        """
        self.setup_media()
        self.logout_user()
        args = ['drm=playready', 'playready_version=3.0',
                'playready_piff=1']
        await self.check_piff_uuid_is_present(args)
        args = ['drm=playready', 'playready_version=3.0',
                'playready_piff=true']
        await self.check_piff_uuid_is_present(args)

    async def test_playready_piff_sample_encryption_with_saio_bug(self):
        """
        PiffSampleEncryptionBox is inserted when playready_piff=true option is used
        """
        self.setup_media()
        self.logout_user()
        args = ['drm=playready', 'playready_version=3.0',
                'playready_piff=1', 'bugs=saio']
        with self.assertRaises(AssertionError):
            await self.check_piff_uuid_is_present(args, expect_errors=True)

    async def test_all_playready_options(self):
        filename = 'hand_made.mpd'
        manifest = manifests.manifest[filename]
        drm_opts = list(manifest.get_drm_options('vod', only={'playready'}))
        extras = [
            manifests.SupportedOptionTuple('drm', len(drm_opts), drm_opts),
            manifests.SupportedOptionTuple(
                'playready_la_url', 2, ['https://some.server/pr', 'http://another.addr/abc']),
        ]
        await self.check_a_manifest_using_all_options(
            filename,
            mode='vod',
            only={'playreadyPiff', 'playreadyVersion'},
            extras=extras)

    async def check_piff_uuid_is_present(self, args: list[str], expect_errors: bool = False) -> None:
        filename = 'hand_made.mpd'
        baseurl = flask.url_for(
            'dash-mpd-v3',
            manifest=filename,
            stream=self.FIXTURES_PATH.name,
            mode='vod')
        baseurl += '?' + '&'.join(args)
        # response = self.client.get(baseurl)
        # xml = etree.parse(io.BytesIO(response.get_data(as_text=False)))
        with ThreadPoolExecutor(max_workers=4) as tpe:
            pool = ConcurrentWorkerPool(tpe)
            dv = ViewsTestDashValidator(
                http_client=self.async_client, mode='vod', url=baseurl, encrypted=True, check_media=True,
                pool=pool, duration=int(self.MEDIA_DURATION // 2))
            self.assertTrue(await dv.load())
            for mf in models.MediaFile.all():
                dv.set_representation_info(mf.representation)
            await dv.validate()
        if dv.has_errors() and not expect_errors:
            for idx, line in enumerate(dv.manifest_text, start=1):
                print(f'{idx:3d}: {line}')
            for err in dv.get_errors():
                print(err)
        self.assertFalse(dv.has_errors(), msg='DASH stream validation failed')
        self.assertEqual(len(dv.manifest.periods), 1)
        piff_uuid = mp4.PiffSampleEncryptionBox.DEFAULT_VALUES['atom_type']
        for adap_set in dv.manifest.periods[0].adaptation_sets:
            for rep in adap_set.representations:
                for seg in rep.media_segments:
                    response = self.client.get(seg.url)
                    self.assertEqual(response.status_code, 200)
                    src = BufferedReader(None, data=response.get_data(as_text=False))
                    atoms = mp4.Mp4Atom.load(src, options={'iv_size': 64})
                    for a in atoms:
                        if a.atom_type != 'moof':
                            continue
                        piff = a.traf.find_child(piff_uuid)
                        self.assertIsNotNone(piff, 'PIFF UUID box is missing')

    def _patch_position_values(self, expected, delta):
        if 'position' in expected:
            expected['position'] += delta
        if 'children' in expected and expected['children'] is not None:
            for child in expected['children']:
                self._patch_position_values(child, delta)

    async def test_different_kids(self) -> None:
        """
        Check that each AdaptationSet has different ContentProtection
        descriptors when the Representations use different KIDs
        """
        self.setup_media()
        await self.check_number_unique_pro_headers(1)

        new_kids: list[str] = [
            'a2c786d0-f9ef-4cb3-b333-cd323a4284a5',
            'db06a8fe-ec16-4de2-9228-2c71e9b856ab',
        ]
        with self.app.app_context():
            for kid in new_kids:
                km_kid = KeyMaterial(hex=kid)
                key = binascii.b2a_hex(PlayReady.generate_content_key(km_kid.raw))
                keypair = models.Key(hkid=km_kid.hex, hkey=key, computed=True)
                models.db.session.add(keypair)
            for idx, name in enumerate(['bbb_a1_enc', 'bbb_a2_enc']):
                mf = models.MediaFile.get(name=name)
                self.assertIsNotNone(mf)
                self.assertIsNotNone(mf.rep)
                rep = mf.get_representation()
                self.assertIsNotNone(rep)
                rep.kids = [new_kids[idx]]
                mf.set_representation(rep)
            models.db.session.commit()
        await self.check_number_unique_pro_headers(3)

    async def check_number_unique_pro_headers(self, expected_pros: int) -> None:
        self.logout_user()
        baseurl = flask.url_for(
            'dash-mpd-v3',
            manifest='hand_made.mpd',
            stream=self.FIXTURES_PATH.name,
            mode='vod')
        args = ['drm=playready-pro', 'acodec=any']
        baseurl += '?' + '&'.join(args)
        response = self.client.get(baseurl)
        self.assertEqual(response.status_code, 200)
        xml = etree.parse(io.BytesIO(response.get_data(as_text=False)))
        with ThreadPoolExecutor(max_workers=4) as tpe:
            pool = ConcurrentWorkerPool(tpe)
            mpd = ViewsTestDashValidator(
                http_client=self.async_client, mode='vod', url=baseurl,
                encrypted=True, check_media=False,
                duration=self.SEGMENT_DURATION, pool=pool)
            await mpd.load(xml=xml.getroot())
            await mpd.validate()
        self.assertFalse(mpd.has_errors())
        self.assertEqual(len(mpd.manifest.periods), 1)
        schemeIdUri = "urn:uuid:" + PlayReady.SYSTEM_ID.lower()
        pro_tag = "{{{0}}}pro".format(mpd.xmlNamespaces['mspr'])
        pro_data: set[bytes] = set()
        for adap_set in mpd.manifest.periods[0].adaptation_sets:
            for prot in adap_set.contentProtection:
                if prot.schemeIdUri != schemeIdUri:
                    continue
                for elt in prot.children():
                    if elt.tag != pro_tag:
                        continue
                    pro = base64.b64decode(elt.text)
                    pro_data.add(pro)
        self.assertEqual(len(pro_data), expected_pros)


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
            PlayreadyTests)

if __name__ == "__main__":
    unittest.main()
