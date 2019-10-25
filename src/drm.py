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
import re
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
import struct
from xml.etree import ElementTree
from Crypto.Cipher import AES
from Crypto.Hash import SHA256

import mp4

class KeyMaterial(object):
    length = 16

    def __init__(self, value=None, hex=None, b64=None, raw=None):
        if value is not None:
            if len(value) == 16:
                self.raw = value
            elif re.match(r'^(0x)?[0-9a-f-]+$', value, re.IGNORECASE):
                if value.startswith('0x'):
                    value = value[2:]
                self.raw = binascii.unhexlify(value.replace('-',''))
            else:
                self.raw = base64.b64decode(value)
        elif raw is not None:
            self.raw = raw
        elif hex is not None:
            self.raw = binascii.unhexlify(hex.replace('-',''))
        elif b64 is not None:
            self.raw = binascii.a2b_base64(b64)
        else:
            raise ValueError("One of value, hex, b64 or raw must be provided")
        if len(self.raw) != self.length:
            raise ValueError("Size {} is invalid".format(len(self.raw)))

    def to_hex(self):
        return binascii.b2a_hex(self.raw)

    def from_hex(self, value):
        self.raw = vale.replace('-','').decode('hex')

    hex = property(to_hex, from_hex)

    def to_base64(self):
        return base64.b64encode(self.raw)

    def from_base64(self, value):
        self.raw = base64.b64decode(value)

    b64 = property(to_base64, from_base64)

    def __len__(self):
        return self.length

class PlayReady(object):
    SYSTEM_ID = "9a04f079-9840-4286-ab92-e65be0885f95"
    RAW_SYSTEM_ID = "9a04f07998404286ab92e65be0885f95".decode("hex")
    TEST_KEY_SEED = base64.b64decode("XVBovsmzhP9gRIZxWfFta3VVRPzVEWmJsazEJ46I")
    TEST_LA_URL = "https://test.playready.microsoft.com/service/rightsmanager.asmx?cfg={cfgs}"
    DRM_AES_KEYSIZE_128 = 16

    def __init__(self, templates, la_url=None, version=None, security_level=150):
        self.templates = templates
        self.version = version
        self.la_url = la_url
        self.security_level = security_level

    @classmethod
    def hex_to_le_guid(clz, guid, raw):
        if raw==True:
            if len(guid)!=16:
                raise ValueError("GUID should be 16 bytes")
            guid = guid.encode('hex')
        else:
            guid = guid.replace('-', '')
        if len(guid)!=32:
            raise ValueError("GUID should be 32 hex characters")
        dword = ''.join([guid[6:8], guid[4:6],guid[2:4],guid[0:2]])
        word1 = ''.join([guid[10:12], guid[8:10]])
        word2 = ''.join([guid[14:16], guid[12:14]])
        # looking at example streams, word 3 appears to be in big endian format! 
        word3 = ''.join([guid[16:18], guid[18:20]]) 
        result = '-'.join([dword, word1, word2, word3, guid[20:]])
        assert len(result) == 36
        if raw == True:
            return result.replace('-','').decode('hex')
        #raise ValueError(guid, result)
        return result

    def generate_checksum(self, keypair):
        guid_kid = PlayReady.hex_to_le_guid(keypair.KID.raw, raw=True)
        if len(guid_kid) != 16:
            raise ValueError("KID should be a raw 16 byte key")
        # checksum = first 8 bytes of AES ECB of kid using key
        cipher = AES.new(keypair.KEY.raw, AES.MODE_ECB)
        msg = cipher.encrypt(guid_kid)
        return msg[:8]

    #https://docs.microsoft.com/en-us/playready/specifications/playready-key-seed
    @classmethod
    def generate_content_key(clz, keyId, keySeed=None):
        """Generate a content key from the key ID"""
        if keySeed is None:
            keySeed = PlayReady.TEST_KEY_SEED
        if len(keyId) != 16:
            raise ValueError("KID should be a raw 16 byte value")
        keyId = PlayReady.hex_to_le_guid(keyId, raw=True)
        if len(keySeed) < 30:
            raise ValueError("Key seed must be at least 30 bytes")
        # Truncate the key seed to 30 bytes, key seed must be at least 30 bytes long.
        truncatedKeySeed = keySeed[:30]
        assert len(keyId)==16
        assert len(truncatedKeySeed)==30
        # Create sha_A_Output buffer.  It is the SHA of the truncatedKeySeed and the keyIdAsBytes
        sha_A = SHA256.new();
        sha_A.update(truncatedKeySeed)
        sha_A.update(keyId)
        sha_A_Output = bytearray(sha_A.digest())

        # Create sha_B_Output buffer.  It is the SHA of the truncatedKeySeed, the keyIdAsBytes, and
        # the truncatedKeySeed again.
        sha_B = SHA256.new()
        sha_B.update(truncatedKeySeed)
        sha_B.update(keyId)
        sha_B.update(truncatedKeySeed)
        sha_B_Output = bytearray(sha_B.digest())

        # Create sha_C_Output buffer.  It is the SHA of the truncatedKeySeed, the keyIdAsBytes,
        # the truncatedKeySeed again, and the keyIdAsBytes again.
        sha_C = SHA256.new()
        sha_C.update(truncatedKeySeed)
        sha_C.update(keyId)
        sha_C.update(truncatedKeySeed)
        sha_C.update(keyId)
        sha_C_Output = bytearray(sha_C.digest())

        contentKey = bytearray(PlayReady.DRM_AES_KEYSIZE_128)
        for i in range(PlayReady.DRM_AES_KEYSIZE_128):
            contentKey[i] = sha_A_Output[i] ^ sha_A_Output[i + PlayReady.DRM_AES_KEYSIZE_128] \
                            ^ sha_B_Output[i] ^ sha_B_Output[i + PlayReady.DRM_AES_KEYSIZE_128] \
                            ^ sha_C_Output[i] ^ sha_C_Output[i + PlayReady.DRM_AES_KEYSIZE_128]
        return contentKey

    def generate_wrmheader(self, representation, keys):
        """Generate WRMHEADER XML document"""
        la_url = self.la_url
        cfgs = []
        kids = []
        for keypair in keys.values():
            guid_kid = PlayReady.hex_to_le_guid(keypair.KID.raw, raw=True)
            rkey = keypair.KEY.raw
            kids.append({
                'kid': guid_kid,
                'checksum': self.generate_checksum(keypair),
            })
            cfg = [
                'kid:' + base64.b64encode(guid_kid),
                'persist:false',
                'sl:'+str(self.security_level)
            ]
            if not keypair.computed:
                cfg.append('contentkey:' + base64.b64encode(rkey))
            cfgs.append('(' + ','.join(cfg) + ')')
        cfgs = ','.join(cfgs)
        if la_url is None:
            la_url = self.TEST_LA_URL
        default_keypair = keys[representation.default_kid.lower()]
        default_key = default_keypair.KEY.raw
        default_kid = PlayReady.hex_to_le_guid(default_keypair.KID.raw, raw=True)
        context = {
            "default_kid": default_kid,
            "kids": kids,
            "la_url": la_url.format(cfgs=cfgs, default_kid=default_keypair.KID.hex)
        }
        #print(context["la_url"])
        context["checksum"] = self.generate_checksum(default_keypair)
        version = self.version
        if version is None:
            if len(keys)==1:
                version = 4.1
            else:
                version = 4.2
        if version==4.2:
            template = self.templates.get_template('drm/wrmheader42.xml')
        elif version==4.1:
            template = self.templates.get_template('drm/wrmheader41.xml')
        else:
            if version != 4.0:
                raise ValueError("PlayReady header version {} has not been implemented".format(version))
            template = self.templates.get_template('drm/wrmheader40.xml')
        xml = template.render(context)
        xml = re.sub(r'[\r\n]', '', xml)
        xml = re.sub(r'>\s+<', '><', xml)
        #raise ValueError(xml)
        wrm = xml.encode('utf-16')
        if ord(wrm[0]) == 0xFF and ord(wrm[1]) == 0xFE:
            # remove UTF-16 byte order mark
            wrm = wrm[2:]
        return wrm

    def generate_pro(self, representation, keys):
        """Generate PlayReady Object (PRO)"""
        wrm = self.generate_wrmheader(representation, keys)
        record = struct.pack('<HH', 0x001, len(wrm)) + wrm
        pro = struct.pack('<IH', len(record)+6, 1) + record
        return pro

    @classmethod
    def parse_pro(clz, src):
        """Parse a PlayReady Object (PRO)"""
        data = src.read(6)
        if len(data) != 6:
            raise IOError("PlayReady Object too small")
        length, object_count = struct.unpack("<IH", data)
        objects = []
        for idx in range(object_count):
            data = src.read(4)
            if len(data) != 4:
                raise IOError("PlayReady Object too small")
            record_type, record_length = struct.unpack("<HH", data)
            record = {
                'type': record_type,
                'length': record_length,
            }
            if record_type == 1:
                prh = src.read(record_length)
                if len(prh) != record_length:
                    raise IOError("PlayReady Object too small")
                record['PlayReadyHeader'] = prh.decode('utf-16')
                record['xml'] = ElementTree.parse(StringIO.StringIO(record['PlayReadyHeader']))
            objects.append(record)
        return record

    def generate_pssh(self, representation, keys):
        """Generate a PlayReady Object (PRO) inside a PSSH box"""
        pro = self.generate_pro(representation, keys)
        pssh_version = 0 if len(keys)==1 else 1
        if isinstance(keys, dict):
            keys = keys.keys()
        keys = map(lambda k: KeyMaterial(k).raw, keys)
        return mp4.ContentProtectionSpecificBox(version=pssh_version,
                                                flags=0,
                                                system_id=PlayReady.SYSTEM_ID,
                                                key_ids=keys,
                                                data=pro)


class ClearKey(object):
    MPD_SYSTEM_ID = "e2719d58-a985-b3c9-781a-b030af78d30e"
    PSSH_SYSTEM_ID = "1077efec-c0b2-4d02-ace3-3c1e52e2fb4b"

    def __init__(self, templates):
        self.templates = templates

    def generate_pssh(self, representation, keys):
        """Generate a Clearkey PSSH box"""
        # see https://www.w3.org/TR/eme-initdata-cenc/
        if isinstance(keys, dict):
            keys = keys.keys()
        keys = map(lambda k: KeyMaterial(k).raw, keys)
        return mp4.ContentProtectionSpecificBox(version=1, flags=0,
                                                system_id=self.PSSH_SYSTEM_ID,
                                                key_ids=keys,
                                                data=None
        )

if __name__ == "__main__":
    import sys
    import utils

    PR_ID = PlayReady.SYSTEM_ID.replace('-','').lower()

    def show_pssh(atom):
        if atom.atom_type=='pssh':
            print(atom)
            if atom.system_id == PR_ID:
                pro = PlayReady.parse_pro(utils.BufferedReader(None, data=atom.data))
                print(pro)
        else:
            for child in atom.children:
                show_pssh(child)

    for filename in sys.argv[1:]:
        parser = mp4.IsoParser()
        atoms = parser.walk_atoms(filename)
        for atom in atoms:
            show_pssh(atom)
