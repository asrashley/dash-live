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
import struct
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
    Test_Key_Seed = base64.b64decode("XVBovsmzhP9gRIZxWfFta3VVRPzVEWmJsazEJ46I")
    DRM_AES_KEYSIZE_128 = 16

    def __init__(self, templates, la_url=None, version=4.0, security_level=150):
        self.templates = templates
        self.version = version
        self.la_url = la_url
        self.security_level = security_level

    def hex_to_le_guid(self, guid, raw):
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

    def generate_checksum(self, kid, key):
        if len(kid) != 16:
            raise ValueError("KID should be a raw 16 byte key")
        if len(key) != 16:
            raise ValueError("Key should be a raw 16 byte key")
        # checksum = first 8 bytes of AES ECB of kid using key
        cipher = AES.new(key, AES.MODE_ECB)
        msg = cipher.encrypt(kid)
        return msg[:8]

    #https://docs.microsoft.com/en-us/playready/specifications/playready-key-seed
    @classmethod
    def generate_content_key(clz, keyId, keySeed=None):
        """Generate a content key from the key ID"""
        if keySeed is None:
            keySeed = PlayReady.Test_Key_Seed
        if len(keyId) != 16:
            raise ValueError("KID should be a raw 16 byte value")
        keyId = self.hex_to_le_guid(keyId, raw=True)
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
        def as_string(d):
            rv = []
            for k,v in d.iteritems():
                rv.append(k+':'+v)
            return ','.join(rv)
        default_keypair = keys[representation.default_kid.lower()]
        raw_key = default_keypair.KEY.raw
        raw_kid = self.hex_to_le_guid(default_keypair.KID.raw, raw=True)
        la_url = self.la_url
        cfg = {
            'kid':  base64.b64encode(raw_kid),
            'persist': 'false',
            'sl': str(self.security_level),
        }
        if not default_keypair.computed:
            cfg['contentkey'] = base64.b64encode(raw_key)
        if la_url is None:
            la_url = "https://test.playready.microsoft.com/service/rightsmanager.asmx?cfg=({cfg})"
        context = {
            "kid": raw_kid,
            "la_url": la_url.format(cfg=as_string(cfg), **cfg)
        }
        context["checksum"] = self.generate_checksum(raw_kid, raw_key)
        if self.version==4.1:
            template = self.templates.get_template('drm/wrmheader41.xml')
        else:
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

    def generate_pssh(self, representation, keys):
        """Generate a PlayReady Object (PRO) inside a PSSH box"""
        pro = self.generate_pro(representation, keys)
        return mp4.ContentProtectionSpecificBox(atom_type='pssh', version=1, flags=0,
                                                system_id=PlayReady.SYSTEM_ID,
                                                key_ids=keys.keys(),
                                                data=pro
        )

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
        return mp4.ContentProtectionSpecificBox(atom_type='pssh', version=1, flags=0,
                                                system_id=self.PSSH_SYSTEM_ID,
                                                key_ids=keys,
                                                data=None
        )
