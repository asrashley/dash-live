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
import re
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
import struct
import sys
import urllib

from xml.etree import ElementTree
from Crypto.Cipher import AES
from Crypto.Hash import SHA256

from mpeg import mp4
from drm.base import DrmBase
from drm.keymaterial import KeyMaterial
from utils.buffered_reader import BufferedReader

class PlayReady(DrmBase):
    MAJOR_VERSIONS = [1.0, 2.0, 3.0, 4.0]
    SYSTEM_ID = "9a04f079-9840-4286-ab92-e65be0885f95"
    SYSTEM_ID_V10 = "79f0049a-4098-8642-ab92-e65be0885f95"
    RAW_SYSTEM_ID = "9a04f07998404286ab92e65be0885f95".decode("hex")
    TEST_KEY_SEED = base64.b64decode(
        "XVBovsmzhP9gRIZxWfFta3VVRPzVEWmJsazEJ46I")
    TEST_LA_URL = "https://test.playready.microsoft.com/service/rightsmanager.asmx?cfg={cfgs}"
    DRM_AES_KEYSIZE_128 = 16

    def __init__(self, templates, la_url=None, version=None, header_version=None,
                 security_level=150):
        """
        :templates: The jinja2 template environment to use
        :la_url: The license URL
        :version: The PlayReady version (1.0 .. 4.0)
        :header_version: The WRMHEADER version (4.0, 4.1, 4.2 or 4.3)
        :security_level: Minimum security level (150, 2000, 3000)
        """
        super(PlayReady, self).__init__(templates)
        self.version = version
        self.header_version = header_version
        self.la_url = la_url
        self.security_level = security_level

    @classmethod
    def hex_to_le_guid(clz, guid, raw):
        if raw is True:
            if len(guid) != 16:
                raise ValueError("GUID should be 16 bytes")
            guid = guid.encode('hex')
        else:
            guid = guid.replace('-', '')
        if len(guid) != 32:
            raise ValueError("GUID should be 32 hex characters")
        dword = ''.join([guid[6:8], guid[4:6], guid[2:4], guid[0:2]])
        word1 = ''.join([guid[10:12], guid[8:10]])
        word2 = ''.join([guid[14:16], guid[12:14]])
        # looking at example streams, word 3 appears to be in big endian
        # format!
        word3 = ''.join([guid[16:18], guid[18:20]])
        result = '-'.join([dword, word1, word2, word3, guid[20:]])
        assert len(result) == 36
        if raw is True:
            return result.replace('-', '').decode('hex')
        return result

    def generate_checksum(self, keypair):
        guid_kid = PlayReady.hex_to_le_guid(keypair.KID.raw, raw=True)
        if len(guid_kid) != 16:
            raise ValueError("KID should be a raw 16 byte key")
        # checksum = first 8 bytes of AES ECB of kid using key
        cipher = AES.new(keypair.KEY.raw, AES.MODE_ECB)
        msg = cipher.encrypt(guid_kid)
        return msg[:8]

    # https://docs.microsoft.com/en-us/playready/specifications/playready-key-seed
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
        # Truncate the key seed to 30 bytes, key seed must be at least 30 bytes
        # long.
        truncatedKeySeed = keySeed[:30]
        assert len(keyId) == 16
        assert len(truncatedKeySeed) == 30
        # Create sha_A_Output buffer.  It is the SHA of the truncatedKeySeed
        # and the keyIdAsBytes
        sha_A = SHA256.new()
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

    def generate_wrmheader(self, la_url, representation, keys, custom_attributes):
        """Generate WRMHEADER XML document"""
        cfgs = []
        kids = []
        for keypair in keys.values():
            guid_kid = PlayReady.hex_to_le_guid(keypair.KID.raw, raw=True)
            rkey = keypair.KEY.raw
            kids.append({
                'kid': guid_kid,
                'alg': keypair.ALG,
                'checksum': self.generate_checksum(keypair),
            })
            cfg = [
                'kid:' + base64.b64encode(guid_kid),
                'persist:false',
                'sl:' + str(self.security_level)
            ]
            if not keypair.computed:
                cfg.append('contentkey:' + base64.b64encode(rkey))
            cfgs.append('(' + ','.join(cfg) + ')')
        cfgs = ','.join(cfgs)
        if la_url is None:
            la_url = self.TEST_LA_URL
        default_keypair = keys[representation.default_kid.lower()]
        default_key = default_keypair.KEY.raw
        default_kid = PlayReady.hex_to_le_guid(
            default_keypair.KID.raw, raw=True)
        if custom_attributes is None:
            custom_attributes = []
        context = {
            "customAttributes": custom_attributes,
            "default_kid": default_kid,
            "default_key": default_key,
            "kids": kids,
            "la_url": la_url.format(cfgs=cfgs,
                                    default_kid=default_keypair.KID.hex,
                                    kids=[a["kid"] for a in kids]
                                    )
        }
        context["checksum"] = self.generate_checksum(default_keypair)
        header_version = self.header_version
        if header_version is None:
            header_version = self.minimum_header_version(keys)
            if self.version is not None:
                if ((header_version == 4.3 and self.version < 4.0) or
                    (header_version == 4.2 and self.version < 3.0) or
                        (header_version == 4.1 and self.version < 2.0)):
                    raise ValueError(
                        '{0} WRMHEADER is not supported by PlayReady v{1}'.format(
                            header_version, self.version
                        ))
        if header_version not in [4.0, 4.1, 4.2, 4.3]:
            raise ValueError(
                "PlayReady header version {} has not been implemented".format(header_version))
        template = self.templates.get_template(
            'drm/wrmheader{0}.xml'.format(int(header_version * 10)))
        xml = template.render(context)
        xml = re.sub(r'[\r\n]', '', xml)
        xml = re.sub(r'>\s+<', '><', xml)
        wrm = xml.encode('utf-16')
        if ord(wrm[0]) == 0xFF and ord(wrm[1]) == 0xFE:
            # remove UTF-16 byte order mark
            wrm = wrm[2:]
        return wrm

    def generate_pro(self, la_url, representation, keys, custom_attributes):
        """Generate PlayReady Object (PRO)"""
        wrm = self.generate_wrmheader(la_url, representation, keys, custom_attributes)
        record = struct.pack('<HH', 0x001, len(wrm)) + wrm
        pro = struct.pack('<IH', len(record) + 6, 1) + record
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
                record['xml'] = ElementTree.parse(
                    StringIO.StringIO(record['PlayReadyHeader']))
            objects.append(record)
        return objects

    def generate_manifest_context(self, stream, keys, cgi_params, la_url=None, locations=None):
        version = cgi_params.get('playready_version')
        if version is not None:
            version = float(version)
        else:
            header_version = self.minimum_header_version(keys)
            version = self.minimum_playready_version(header_version)
        if la_url is None:
            la_url = cgi_params.get('playready_la_url')
            if la_url is not None:
                la_url = urllib.unquote_plus(la_url)
            elif stream.playready_la_url is not None:
                la_url = stream.playready_la_url
            else:
                la_url = self.la_url
        if locations is None:
            locations = {'pro', 'cenc', 'moov'}
        rv = {
            'laurl': la_url,
            'scheme_id': self.dash_scheme_id(version),
            'version': version,
        }
        if 'pro' in locations:
            rv['pro'] = lambda rep, keys, cattr=None: self.generate_pro(
                la_url, rep, keys, cattr)
        # PlayReady v1.0 (PIFF) mode only allows an mspr:pro element
        if version > 1.0:
            if 'cenc' in locations:
                rv['cenc'] = lambda rep, keys, cattr=None: self.generate_pssh(
                    la_url, rep, keys, cattr)
            if 'moov' in locations:
                rv['moov'] = lambda rep, keys, cattr=None: self.generate_pssh(
                    la_url, rep, keys, cattr)
        return rv

    def generate_pssh(self, la_url, representation, keys, custom_attributes=None):
        """Generate a PlayReady Object (PRO) inside a PSSH box"""
        pro = self.generate_pro(la_url, representation, keys, custom_attributes)
        if len(keys) < 2:
            return mp4.ContentProtectionSpecificBox(
                version=0, flags=0, system_id=PlayReady.RAW_SYSTEM_ID,
                key_ids=[], data=pro)
        if isinstance(keys, dict):
            keys = keys.keys()
        keys = map(lambda k: KeyMaterial(k).raw, keys)
        return mp4.ContentProtectionSpecificBox(
            version=1, flags=0, system_id=PlayReady.RAW_SYSTEM_ID,
            key_ids=keys, data=pro)

    def dash_scheme_id(self, version=None):
        """
        Returns the schemeIdUri for PlayReady
        """
        if version is None:
            version = self.version
        if version == 1.0:
            return "urn:uuid:{0}".format(self.SYSTEM_ID_V10)
        return "urn:uuid:{0}".format(self.SYSTEM_ID)

    def update_traf_if_required(self, cgi_params, traf):
        version = cgi_params.get('playready_version')
        piff = cgi_params.get('playready_piff', 'false')
        piff = piff in ["1", "true"]
        if version is not None:
            version = float(version)
        else:
            version = self.version
        if version != 1.0 and not piff:
            return False
        senc = traf.find_child('senc')
        if senc is None:
            return False
        pos = traf.index('saiz')
        piff = mp4.PiffSampleEncryptionBox.clone_from_senc(senc)
        traf.insert_child(pos, piff)
        return True

    def minimum_header_version(self, keys):
        """
        Calculate the mimimum playready header version that supports the supplied keys
        """
        cenc_alg = 'AESCTR'
        for keypair in keys.values():
            cenc_alg = keypair.ALG
        if cenc_alg != 'AESCTR':
            header_version = 4.3
        elif len(keys) == 1:
            if self.version is not None and self.version >= 2.0:
                header_version = 4.1
            else:
                header_version = 4.0
        else:
            header_version = 4.2
        return header_version

    def minimum_playready_version(self, header_version):
        """
        Calculate minimum Playready version based upon the header version
        """
        if header_version == 4.3:
            return 4.0
        if header_version == 4.2:
            return 3.0
        return 2.0

    @classmethod
    def is_supported_scheme_id(cls, uri):
        uri = uri.lower()
        if not uri.startswith("urn:uuid:"):
            return False
        return uri[9:] in {cls.SYSTEM_ID, cls.SYSTEM_ID_V10}


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        data = base64.b64decode(arg)
        src = BufferedReader(None, data=data)
        if data[4:8] == 'pssh':
            atoms = mp4.Mp4Atom.load(src)
            assert atoms[0].atom_type == 'pssh'
            src = BufferedReader(None, data=atoms[0].data.data)
        objects = PlayReady.parse_pro(src)
        for pro in objects:
            print(pro)
