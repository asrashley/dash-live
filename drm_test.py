import base64
import binascii
import os
import unittest
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

import jinja2
from media.segment import Representation

import mp4
import utils
from drm import KeyMaterial, PlayReady, ClearKey

class KeyStub(object):
    def __init__(self, kid, key):
        self.KID = KeyMaterial(hex=kid)
        self.KEY = KeyMaterial(hex=key)

class PlayreadyTests(unittest.TestCase):
    def setUp(self):
        self.templates = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                os.path.join(os.path.dirname(__file__),'templates')
            ),
            extensions=['jinja2.ext.autoescape'],
            trim_blocks=False,
        )
        self.templates.filters['base64'] = utils.toBase64
        self.keys = {}
        for kid, key in [
                ("1AB45440532C439994DC5C5AD9584BAC", "ccc0f2b3b279926496a7f5d25da692f6")]:
            self.keys[kid.lower()] = KeyStub(kid, key)
        self.la_url='https://amssamples.keydelivery.mediaservices.windows.net/PlayReady/'

    def test_guid_generation(self):
        default_kid =   '1AB45440-532C-4399-94DC-5C5AD9584BAC'.lower()
        expected_uuid = '4054b41a-2c53-9943-94dc-5c5ad9584bac'
        mspr = PlayReady(self.templates, la_url=self.la_url)
        guid = mspr.hex_to_le_guid(default_kid, raw=False)
        self.assertEqual(expected_uuid, guid)
        raw_kid = binascii.a2b_hex(guid.replace('-', ''))
        self.assertEqual(len(raw_kid), 16)
        hex_kid = raw_kid.encode('hex')
        hex_uuid = expected_uuid.replace('-','')
        raw_uuid = binascii.a2b_hex(hex_uuid)
        self.assertEqual(len(raw_uuid), 16)
        for i in range(len(raw_kid)):
            self.assertEqual(ord(raw_kid[i]), ord(raw_uuid[i]),
                             'Expected 0x{:02x} got 0x{:02x} at {}'.format(ord(raw_kid[i]), ord(raw_uuid[i]), i))
        self.assertEqual(expected_uuid.replace('-',''), raw_kid.encode('hex'))
        self.assertEqual(expected_uuid.replace('-','').decode('hex'), raw_kid)
        base64_kid = base64.standard_b64encode(raw_kid)
        self.assertEqual(r'QFS0GixTmUOU3Fxa2VhLrA==', base64_kid)

    def test_content_key_generation(self):
        #https://brokenpipe.wordpress.com/2016/10/06/generating-a-playready-content-key-using-a-key-seed-and-key-id/
        mspr = PlayReady(self.templates, la_url=self.la_url)
        kid='01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-','').decode('hex')
        expected_key=base64.b64decode('GUf166PQbx+sgBADjyBMvw==')
        key = PlayReady.generate_content_key(kid)
        self.assertEqual(binascii.b2a_hex(key), binascii.b2a_hex(expected_key))

        # Unified streaming example
        #kid='c001de8e567b5fcfbc22c565ed5bda24'.decode('hex')
        #expected_key='533a583a843436a536fbe2a5821c4b6c'.decode('hex')
        #key = mspr.generate_content_key(kid)
        #self.assertEqual(binascii.b2a_hex(key), binascii.b2a_hex(expected_key))

        # http://profficialsite.origin.mediaservices.windows.net/228e2071-c79b-4bb7-b999-0f74801c924a/tearsofsteel_1080p_60s_24fps.6000kbps.1920x1080.h264-8b.2ch.128kbps.aac.avsep.cenc.mp4
        KID='a2c786d0f9ef4cb3b333cd323a4284a5'.decode('hex')
        CEK='4edb7704cdbf03617f4800bd878a6df2'.decode('hex')
        key = PlayReady.generate_content_key(KID)
        self.assertEqual(binascii.b2a_hex(key), binascii.b2a_hex(CEK))

    def test_checksum_generation(self):
        mspr = PlayReady(self.templates, la_url=self.la_url)
        kid_hex='01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-','')
        key=base64.b64decode('GUf166PQbx+sgBADjyBMvw==')
        expected_checksum = base64.b64decode(r'EV/EKanLDy4=')
        guid_kid = mspr.hex_to_le_guid(kid_hex.decode('hex'), raw=True)
        checksum = mspr.generate_checksum(guid_kid, key)
        self.assertEqual(binascii.b2a_hex(checksum), binascii.b2a_hex(expected_checksum))

    def test_wrm_generation(self):
        self.maxDiff = None
        mspr = PlayReady(self.templates, la_url=self.la_url)
        representation = Representation(id='V1', default_kid=self.keys.keys()[0])
        mspr.generate_checksum = lambda kid, key: binascii.a2b_base64('Xy6jKG4PJSY=')
        wrm = mspr.generate_wrmheader(representation, self.keys)
        expected_wrm=r'<WRMHEADER xmlns="http://schemas.microsoft.com/DRM/2007/03/PlayReadyHeader" version="4.0.0.0"><DATA><PROTECTINFO><KEYLEN>16</KEYLEN><ALGID>AESCTR</ALGID></PROTECTINFO><KID>QFS0GixTmUOU3Fxa2VhLrA==</KID><CHECKSUM>Xy6jKG4PJSY=</CHECKSUM><LA_URL>https://amssamples.keydelivery.mediaservices.windows.net/PlayReady/</LA_URL><CUSTOMATTRIBUTES><IIS_DRM_VERSION>8.0.1907.32</IIS_DRM_VERSION></CUSTOMATTRIBUTES></DATA></WRMHEADER>'.encode('utf-16')
        self.assertEqual(expected_wrm.decode('utf-16'), wrm.decode('utf-16'))
        if ord(expected_wrm[0]) == 0xFF and ord(expected_wrm[1]) == 0xFE:
            # remove UTF-16 byte order mark
            expected_wrm = expected_wrm[2:]
        self.assertEqual(expected_wrm, wrm)


    expected_pro = r'VAMAAAEAAQBKAzwAVwBSAE0ASABFAEEARABFAFIAIAB4AG0AbABuAHMAPQAiAGgAdAB0AHAAOgAvAC8AcwBjAGgAZQBtAGEAcwAuAG0AaQBjAHIAbwBzAG8AZgB0AC4AYwBvAG0ALwBEAFIATQAvADIAMAAwADcALwAwADMALwBQAGwAYQB5AFIAZQBhAGQAeQBIAGUAYQBkAGUAcgAiACAAdgBlAHIAcwBpAG8AbgA9ACIANAAuADAALgAwAC4AMAAiAD4APABEAEEAVABBAD4APABQAFIATwBUAEUAQwBUAEkATgBGAE8APgA8AEsARQBZAEwARQBOAD4AMQA2ADwALwBLAEUAWQBMAEUATgA+ADwAQQBMAEcASQBEAD4AQQBFAFMAQwBUAFIAPAAvAEEATABHAEkARAA+ADwALwBQAFIATwBUAEUAQwBUAEkATgBGAE8APgA8AEsASQBEAD4AUQBGAFMAMABHAGkAeABUAG0AVQBPAFUAMwBGAHgAYQAyAFYAaABMAHIAQQA9AD0APAAvAEsASQBEAD4APABDAEgARQBDAEsAUwBVAE0APgBYAHkANgBqAEsARwA0AFAASgBTAFkAPQA8AC8AQwBIAEUAQwBLAFMAVQBNAD4APABMAEEAXwBVAFIATAA+AGgAdAB0AHAAcwA6AC8ALwBhAG0AcwBzAGEAbQBwAGwAZQBzAC4AawBlAHkAZABlAGwAaQB2AGUAcgB5AC4AbQBlAGQAaQBhAHMAZQByAHYAaQBjAGUAcwAuAHcAaQBuAGQAbwB3AHMALgBuAGUAdAAvAFAAbABhAHkAUgBlAGEAZAB5AC8APAAvAEwAQQBfAFUAUgBMAD4APABDAFUAUwBUAE8ATQBBAFQAVABSAEkAQgBVAFQARQBTAD4APABJAEkAUwBfAEQAUgBNAF8AVgBFAFIAUwBJAE8ATgA+ADgALgAwAC4AMQA5ADAANwAuADMAMgA8AC8ASQBJAFMAXwBEAFIATQBfAFYARQBSAFMASQBPAE4APgA8AC8AQwBVAFMAVABPAE0AQQBUAFQAUgBJAEIAVQBUAEUAUwA+ADwALwBEAEEAVABBAD4APAAvAFcAUgBNAEgARQBBAEQARQBSAD4A'
    def test_pro_generation(self):
        self.maxDiff = None
        mspr = PlayReady(self.templates, la_url=self.la_url)
        representation = Representation(id='V1', default_kid=self.keys.keys()[0])
        mspr.generate_checksum = lambda kid, key: binascii.a2b_base64('Xy6jKG4PJSY=')
        pro = base64.b64encode(mspr.generate_pro(representation, self.keys))
        self.assertEqual(pro, self.expected_pro)

    def test_pssh_generation(self):
        mspr = PlayReady(self.templates, la_url=self.la_url)
        representation = Representation(id='V1', default_kid=self.keys.keys()[0])
        mspr.generate_checksum = lambda kid, key: binascii.a2b_base64('Xy6jKG4PJSY=')
        pssh = mspr.generate_pssh(representation, self.keys).encode()
        expected_len = 4 + 4 # Atom(length, 'pssh')
        expected_len += 4 # FullBox(version, flags)
        # PSSH(SystemID, KID_count, KIDs, DataSize, Data)
        pro = base64.b64decode(self.expected_pro)
        expected_len +=  16 + 4 + 16*len(self.keys) + 4 + len(pro) # PSSH
        self.assertEqual(len(pssh), expected_len)
        parser = mp4.IsoParser()
        atoms = parser.walk_atoms(StringIO.StringIO(pssh))
        self.assertEqual(len(atoms), 1)
        self.assertEqual(atoms[0].atom_type, 'pssh')
        self.assertTrue(isinstance(atoms[0], mp4.ContentProtectionSpecificBox))
        self.assertEqual(len(atoms[0].key_ids), len(self.keys))
        self.assertEqual(atoms[0].system_id, PlayReady.SYSTEM_ID.replace('-',''))
        self.assertEqual(atoms[0].data.encode('hex'), pro.encode('hex'))

class ClearkeyTests(unittest.TestCase):
    def setUp(self):
        self.templates = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                os.path.join(os.path.dirname(__file__),'templates')
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
            print(kid, self.keys[kid].KID.hex,self.keys[kid].KEY.hex)
        self.la_url='http://localhost:9080/clearkey'

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
        representation = Representation(id='V1', default_kid=self.keys.keys()[0])
        keys = self.keys.keys()
        keys.sort()
        pssh = ck.generate_pssh(representation, keys).encode()
        self.assertBuffersEqual(expected_pssh, pssh)

if __name__ == "__main__":
    unittest.main()

