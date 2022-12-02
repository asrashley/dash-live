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
import binascii
import os
import unittest
import sys

import jinja2

_src = os.path.join(os.path.dirname(__file__), "..", "src")
if _src not in sys.path:
    sys.path.append(_src)

import utils
from dash.representation import Representation
import mp4
from drm.clearkey import ClearKey
from drm.playready import PlayReady
from drm.keymaterial import KeyMaterial

class KeyStub(object):
    def __init__(self, kid, key, alg=None):
        self.KID = KeyMaterial(hex=kid)
        self.KEY = KeyMaterial(hex=key)
        self.ALG = 'AESCTR' if alg is None else alg
        self.computed = False


class PlayreadyTests(unittest.TestCase):
    def setUp(self):
        self.templates = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                os.path.join(os.path.dirname(__file__), '..', 'templates')
            ),
            extensions=['jinja2.ext.autoescape'],
            trim_blocks=False,
        )
        self.templates.filters['base64'] = utils.toBase64
        self.templates.filters['xmlSafe'] = utils.xmlSafe
        self.keys = {}
        for kid, key in [
                ("1AB45440532C439994DC5C5AD9584BAC", "ccc0f2b3b279926496a7f5d25da692f6")]:
            self.keys[kid.lower()] = KeyStub(kid, key)
        self.la_url = 'https://amssamples.keydelivery.mediaservices.windows.net/PlayReady/'
        self.namespaces = {
            'prh': 'http://schemas.microsoft.com/DRM/2007/03/PlayReadyHeader',
        }

    def test_guid_generation(self):
        default_kid = '1AB45440-532C-4399-94DC-5C5AD9584BAC'.lower()
        expected_uuid = '4054b41a-2c53-9943-94dc-5c5ad9584bac'
        mspr = PlayReady(self.templates, la_url=self.la_url)
        guid = mspr.hex_to_le_guid(default_kid, raw=False)
        self.assertEqual(expected_uuid, guid)
        raw_kid = binascii.a2b_hex(guid.replace('-', ''))
        self.assertEqual(len(raw_kid), 16)
        hex_uuid = expected_uuid.replace('-', '')
        raw_uuid = binascii.a2b_hex(hex_uuid)
        self.assertEqual(len(raw_uuid), 16)
        for i in range(len(raw_kid)):
            self.assertEqual(ord(raw_kid[i]), ord(raw_uuid[i]),
                             'Expected 0x{:02x} got 0x{:02x} at {}'.format(ord(raw_kid[i]), ord(raw_uuid[i]), i))
        self.assertEqual(expected_uuid.replace('-', ''), raw_kid.encode('hex'))
        self.assertEqual(expected_uuid.replace('-', '').decode('hex'), raw_kid)
        base64_kid = base64.standard_b64encode(raw_kid)
        self.assertEqual(r'QFS0GixTmUOU3Fxa2VhLrA==', base64_kid)

    def test_content_key_generation(self):
        # https://brokenpipe.wordpress.com/2016/10/06/generating-a-playready-content-key-using-a-key-seed-and-key-id/
        kid = '01020304-0506-0708-090A-AABBCCDDEEFF'.replace(
            '-', '').decode('hex')
        expected_key = base64.b64decode('GUf166PQbx+sgBADjyBMvw==')
        key = PlayReady.generate_content_key(kid)
        self.assertEqual(binascii.b2a_hex(key), binascii.b2a_hex(expected_key))

        # Unified streaming example
        # kid='c001de8e567b5fcfbc22c565ed5bda24'.decode('hex')
        # expected_key='533a583a843436a536fbe2a5821c4b6c'.decode('hex')
        # mspr = PlayReady(self.templates, la_url=self.la_url)
        # key = mspr.generate_content_key(kid)
        # self.assertEqual(binascii.b2a_hex(key), binascii.b2a_hex(expected_key))

        # http://profficialsite.origin.mediaservices.windows.net/228e2071-c79b-4bb7-b999-0f74801c924a/tearsofsteel_1080p_60s_24fps.6000kbps.1920x1080.h264-8b.2ch.128kbps.aac.avsep.cenc.mp4
        KID = 'a2c786d0f9ef4cb3b333cd323a4284a5'.decode('hex')
        CEK = '4edb7704cdbf03617f4800bd878a6df2'.decode('hex')
        key = PlayReady.generate_content_key(KID)
        self.assertEqual(binascii.b2a_hex(key), binascii.b2a_hex(CEK))

    def test_checksum_generation(self):
        mspr = PlayReady(self.templates, la_url=self.la_url)
        kid_hex = '01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-', '')
        key_hex = base64.b64decode('GUf166PQbx+sgBADjyBMvw==').encode('hex')
        expected_checksum = base64.b64decode(r'EV/EKanLDy4=')
        keypair = KeyStub(kid_hex, key_hex)
        checksum = mspr.generate_checksum(keypair)
        self.assertEqual(
            binascii.b2a_hex(checksum),
            binascii.b2a_hex(expected_checksum))

    def test_wrm_generation(self):
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
            self.templates,
            la_url=self.la_url,
            version=2.0,
            header_version=4.0)
        representation = Representation(
            id='V1', default_kid=self.keys.keys()[0])
        mspr.generate_checksum = lambda keypair: binascii.a2b_base64(
            'Xy6jKG4PJSY=')
        wrm = mspr.generate_wrmheader(representation, self.keys)
        self.assertEqual(expected_wrm.decode('utf-16'), wrm.decode('utf-16'))
        if ord(expected_wrm[0]) == 0xFF and ord(expected_wrm[1]) == 0xFE:
            # remove UTF-16 byte order mark
            expected_wrm = expected_wrm[2:]
        self.assertEqual(expected_wrm, wrm)

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

    def test_pro_generation(self):
        self.maxDiff = None
        mspr = PlayReady(
            self.templates,
            la_url=self.la_url,
            version=2.0,
            header_version=4.0)
        representation = Representation(
            id='V1', default_kid=self.keys.keys()[0])
        mspr.generate_checksum = lambda keypair: binascii.a2b_base64(
            'Xy6jKG4PJSY=')
        pro = base64.b64encode(mspr.generate_pro(representation, self.keys))
        self.assertEqual(pro, self.expected_pro)

    def test_parsing_pro_v4_0(self):
        """
        Check parsing of a pre-defined PlayReady Object (PRO)
        """
        mspr = PlayReady(
            self.templates,
            la_url=self.la_url,
            header_version=4.0)
        mspr.generate_checksum = lambda keypair: binascii.a2b_base64(
            'Xy6jKG4PJSY=')
        e_pro = PlayReady.parse_pro(
            utils.BufferedReader(
                None, data=base64.b64decode(
                    self.expected_pro)))
        xml = e_pro[0]['xml']
        self.assertEqual(xml.getroot().get("version"),
                         '{:02.1f}.0.0'.format(mspr.header_version))
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
        guid = PlayReady.hex_to_le_guid(self.keys.keys()[0], raw=False)
        self.assertEqual(
            base64.b64decode(
                kid[0].text).encode('hex'), guid.replace(
                '-', ''))

    def test_pssh_generation_v4_0(self):
        """Generate and parse PlayReady Header v4.0.0.0"""
        self.assertEqual(len(self.keys), 1)
        mspr = PlayReady(
            self.templates,
            la_url=self.la_url,
            header_version=4.0)
        representation = Representation(id='V1', default_kid=self.keys.keys()[0],
                                        kids=self.keys.keys())
        mspr.generate_checksum = lambda keypair: binascii.a2b_base64(
            'Xy6jKG4PJSY=')
        pssh = mspr.generate_pssh(representation, self.keys).encode()
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
        src = utils.BufferedReader(None, data=pssh)
        atoms = parser.walk_atoms(src)
        self.assertEqual(len(atoms), 1)
        self.assertEqual(atoms[0].atom_type, 'pssh')
        self.assertTrue(isinstance(atoms[0], mp4.ContentProtectionSpecificBox))
        with self.assertRaises(AttributeError):
            print atoms[0].key_ids
        self.assertEqual(atoms[0].system_id, PlayReady.RAW_SYSTEM_ID)
        self.assertEqual(
            atoms[0].data.encode('hex'),
            expected_pro.encode('hex'))
        actual_pro = mspr.parse_pro(
            utils.BufferedReader(
                None, data=atoms[0].data))
        self.assertEqual(actual_pro[0]['xml'].getroot().get("version"),
                         '4.0.0.0')
        algid = actual_pro[0]['xml'].findall('./prh:DATA/prh:PROTECTINFO/prh:ALGID',
                                             self.namespaces)
        self.assertEqual(len(algid), 1)
        self.assertEqual(algid[0].text, "AESCTR")
        keylen = actual_pro[0]['xml'].findall('./prh:DATA/prh:PROTECTINFO/prh:KEYLEN',
                                              self.namespaces)
        self.assertEqual(len(keylen), 1)
        self.assertEqual(keylen[0].text, "16")
        kid = actual_pro[0]['xml'].findall(
            './prh:DATA/prh:KID', self.namespaces)
        self.assertEqual(len(kid), 1)
        guid = PlayReady.hex_to_le_guid(keys.keys()[0], raw=False)
        self.assertEqual(
            base64.b64decode(
                kid[0].text).encode('hex'), guid.replace(
                '-', ''))

    def test_pssh_generation_v4_1(self):
        """Generate and parse PlayReady Header v4.1.0.0"""
        self.assertEqual(len(self.keys), 1)
        mspr = PlayReady(
            self.templates,
            la_url=self.la_url,
            header_version=4.1)
        representation = Representation(id='V1', default_kid=self.keys.keys()[0],
                                        kids=self.keys.keys())
        mspr.generate_checksum = lambda keypair: binascii.a2b_base64(
            'Xy6jKG4PJSY=')
        pssh = mspr.generate_pssh(representation, self.keys).encode()
        self.check_generated_pssh_v4_1(self.keys, mspr, pssh)

    def check_generated_pssh_v4_1(self, keys, mspr, pssh):
        """
        Check the PSSH matches the v4.1.0.0 Schema
        """
        parser = mp4.IsoParser()
        src = utils.BufferedReader(None, data=pssh)
        atoms = parser.walk_atoms(src)
        self.assertEqual(len(atoms), 1)
        self.assertEqual(atoms[0].atom_type, 'pssh')
        self.assertTrue(isinstance(atoms[0], mp4.ContentProtectionSpecificBox))
        with self.assertRaises(AttributeError):
            print atoms[0].key_ids
        self.assertEqual(atoms[0].system_id, PlayReady.RAW_SYSTEM_ID)
        actual_pro = mspr.parse_pro(
            utils.BufferedReader(
                None, data=atoms[0].data))
        self.assertEqual(
            actual_pro[0]['xml'].getroot().get("version"),
            '4.1.0.0')
        kid = actual_pro[0]['xml'].findall(
            './prh:DATA/prh:PROTECTINFO/prh:KID', self.namespaces)
        self.assertEqual(len(kid), 1)
        self.assertEqual(kid[0].get("ALGID"), "AESCTR")
        self.assertEqual(kid[0].get("CHECKSUM"), 'Xy6jKG4PJSY=')
        guid = PlayReady.hex_to_le_guid(keys.keys()[0], raw=False)
        self.assertEqual(
            base64.b64decode(
                kid[0].get("VALUE")).encode('hex'), guid.replace(
                '-', ''))

    def test_pssh_generation_v4_2(self):
        """Generate and parse PlayReady Header v4.2.0.0"""
        keys = {}
        for kid, key in [
                ("1AB45440532C439994DC5C5AD9584BAC",
                 "ccc0f2b3b279926496a7f5d25da692f6"),
                ("db06a8feec164de292282c71e9b856ab", "3179923adf3c929892951e62f93a518a")]:
            keys[kid.lower()] = KeyStub(kid, key)
        mspr = PlayReady(
            self.templates,
            la_url=self.la_url,
            header_version=4.2)
        representation = Representation(
            id='V1', default_kid=keys.keys()[0], kids=keys.keys())
        pssh = mspr.generate_pssh(representation, keys).encode()
        self.check_generated_pssh_v4_2(keys, mspr, pssh)

    def check_generated_pssh_v4_2(self, keys, mspr, pssh):
        """
        Check the PSSH matches the v4.2.0.0 Schema
        """
        parser = mp4.IsoParser()
        src = utils.BufferedReader(None, data=pssh)
        atoms = parser.walk_atoms(src)
        self.assertEqual(len(atoms), 1)
        self.assertEqual(atoms[0].atom_type, 'pssh')
        self.assertTrue(isinstance(atoms[0], mp4.ContentProtectionSpecificBox))
        self.assertEqual(len(atoms[0].key_ids), len(keys))
        self.assertEqual(atoms[0].system_id, PlayReady.RAW_SYSTEM_ID)
        actual_pro = mspr.parse_pro(
            utils.BufferedReader(
                None, data=atoms[0].data))
        self.assertEqual(
            actual_pro[0]['xml'].getroot().get("version"),
            '4.2.0.0')
        kids = actual_pro[0]['xml'].findall('./prh:DATA/prh:PROTECTINFO/prh:KIDS/prh:KID',
                                            self.namespaces)
        guid_map = {}
        for keypair in keys.values():
            guid = PlayReady.hex_to_le_guid(keypair.KID.raw, raw=True)
            guid = base64.b64encode(guid)
            guid_map[guid] = keypair
        self.assertEqual(len(kids), len(keys))
        for kid in kids:
            self.assertEqual(kid.get("ALGID"), "AESCTR")
            keypair = guid_map[kid.get("VALUE")]
            checksum = mspr.generate_checksum(keypair)
            checksum = base64.b64encode(checksum)
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
            self.templates,
            la_url=self.la_url,
            header_version=4.3)
        representation = Representation(
            id='V1', default_kid=keys.keys()[0], kids=keys.keys())
        pssh = mspr.generate_pssh(representation, keys).encode()
        self.check_generated_pssh_v4_3(keys, mspr, pssh)

    def check_generated_pssh_v4_3(self, keys, mspr, pssh):
        """
        Check the PSSH matches the v4.3.0.0 Schema
        """
        parser = mp4.IsoParser()
        src = utils.BufferedReader(None, data=pssh)
        atoms = parser.walk_atoms(src)
        self.assertEqual(len(atoms), 1)
        self.assertEqual(atoms[0].atom_type, 'pssh')
        self.assertTrue(isinstance(atoms[0], mp4.ContentProtectionSpecificBox))
        self.assertEqual(len(atoms[0].key_ids), len(keys))
        self.assertEqual(atoms[0].system_id, PlayReady.RAW_SYSTEM_ID)
        actual_pro = mspr.parse_pro(
            utils.BufferedReader(
                None, data=atoms[0].data))
        self.assertEqual(
            actual_pro[0]['xml'].getroot().get("version"),
            '4.3.0.0')

        kids = actual_pro[0]['xml'].findall('./prh:DATA/prh:PROTECTINFO/prh:KIDS/prh:KID',
                                            self.namespaces)
        guid_map = {}
        for keypair in keys.values():
            guid = PlayReady.hex_to_le_guid(keypair.KID.raw, raw=True)
            guid = base64.b64encode(guid)
            guid_map[guid] = keypair
        self.assertEqual(len(kids), len(keys))
        for kid in kids:
            self.assertEqual(kid.get("ALGID"), "AESCBC")
            keypair = guid_map[kid.get("VALUE")]
            checksum = mspr.generate_checksum(keypair)
            checksum = base64.b64encode(checksum)
            self.assertEqual(kid.get("CHECKSUM"), checksum)

    def test_pssh_generation_auto_header_version(self):
        """
        Generate and parse PlayReady object where header version automatically
        chosen
        """
        self.assertEqual(len(self.keys), 1)
        mspr = PlayReady(self.templates, la_url=self.la_url, version=1.0)
        representation = Representation(id='V1', default_kid=self.keys.keys()[0],
                                        kids=self.keys.keys())
        mspr.generate_checksum = lambda keypair: binascii.a2b_base64(
            'Xy6jKG4PJSY=')

        # check v4.0 (as defined in PlayReady v1.0)
        pssh = mspr.generate_pssh(representation, self.keys).encode()
        self.check_generated_pssh_v4_0(self.keys, mspr, pssh)
        mspr.version = None
        pssh = mspr.generate_pssh(representation, self.keys).encode()
        self.check_generated_pssh_v4_0(self.keys, mspr, pssh)

        # check v4.1 (as defined in PlayReady v2.0)
        mspr.version = 2.0
        pssh = mspr.generate_pssh(representation, self.keys).encode()
        self.check_generated_pssh_v4_1(self.keys, mspr, pssh)

        # check v4.2 (as defined in PlayReady v3.0)
        keys = {}
        for kid, key in [
                ("1AB45440532C439994DC5C5AD9584BAC",
                 "ccc0f2b3b279926496a7f5d25da692f6"),
                ("db06a8feec164de292282c71e9b856ab", "3179923adf3c929892951e62f93a518a")]:
            keys[kid.lower()] = KeyStub(kid, key, alg='AESCTR')
        mspr.version = 3.0
        pssh = mspr.generate_pssh(representation, keys).encode()
        self.check_generated_pssh_v4_2(keys, mspr, pssh)
        mspr.version = None
        pssh = mspr.generate_pssh(representation, keys).encode()
        self.check_generated_pssh_v4_2(keys, mspr, pssh)

        # check v4.3 (as defined in PlayReady v4.0)
        keys = {}
        for kid, key in [
                ("1AB45440532C439994DC5C5AD9584BAC",
                 "ccc0f2b3b279926496a7f5d25da692f6"),
                ("db06a8feec164de292282c71e9b856ab", "3179923adf3c929892951e62f93a518a")]:
            keys[kid.lower()] = KeyStub(kid, key, alg='AESCBC')
        mspr.version = 4.0
        pssh = mspr.generate_pssh(representation, keys).encode()
        self.check_generated_pssh_v4_3(keys, mspr, pssh)
        mspr.version = None
        pssh = mspr.generate_pssh(representation, keys).encode()
        self.check_generated_pssh_v4_3(keys, mspr, pssh)


class ClearkeyTests(unittest.TestCase):
    def setUp(self):
        self.templates = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                os.path.join(os.path.dirname(__file__), 'templates')
            ),
            extensions=['jinja2.ext.autoescape'],
            trim_blocks=False,
        )
        self.templates.filters['base64'] = utils.toBase64
        self.keys = {
            "0123456789012345".encode('hex'): "ccc0f2b3b279926496a7f5d25da692f6",
            "ABCDEFGHIJKLMNOP".encode('hex'): "ccc0f2b3b279926496a7f5d25da692f6",
        }
        for kid in self.keys.keys():
            self.keys[kid] = KeyStub(kid, self.keys[kid])
        self.la_url = 'http://localhost:9080/clearkey'

    def assertBuffersEqual(self, a, b):
        self.assertEqual(len(a), len(b))
        for idx in range(len(a)):
            self.assertEqual(ord(a[idx]), ord(b[idx]),
                             'Expected 0x{:02x} got 0x{:02x} at position {}'.format(ord(a[idx]), ord(b[idx]), idx))

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
        tests = os.environ["TESTS"].split(',')
        for idx, t in enumerate(tests):
            if not t.startswith('drm_test.'):
                tests[idx] = 'drm_test.' + tests[idx]
        return unittest.loader.TestLoader().loadTestsFromNames(tests)

if __name__ == "__main__":
    unittest.main()
