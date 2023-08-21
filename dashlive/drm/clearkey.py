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

import binascii

from dashlive.mpeg.mp4 import ContentProtectionSpecificBox
from .base import DrmBase
from .keymaterial import KeyMaterial

class ClearKey(DrmBase):
    MPD_SYSTEM_ID = "e2719d58-a985-b3c9-781a-b030af78d30e"
    PSSH_SYSTEM_ID = "1077efec-c0b2-4d02-ace3-3c1e52e2fb4b"
    RAW_PSSH_SYSTEM_ID = binascii.a2b_hex(PSSH_SYSTEM_ID.replace('-', ''))

    def dash_scheme_id(self):
        return f"urn:uuid:{self.MPD_SYSTEM_ID}"

    def generate_manifest_context(self, stream, keys, cgi_params, la_url=None, locations=None):
        if locations is None:
            locations = {'cenc', 'moov'}
        rv = {
            'scheme_id': self.dash_scheme_id(),
            'laurl': la_url,
        }
        if 'cenc' in locations:
            rv['cenc'] = self.generate_pssh
        if 'moov' in locations:
            rv['moov'] = self.generate_pssh
        return rv

    def generate_pssh(self, representation, keys):
        """Generate a Clearkey PSSH box"""
        # see https://www.w3.org/TR/eme-initdata-cenc/
        if isinstance(keys, dict):
            keys = list(keys.keys())
        keys = [KeyMaterial(k).raw for k in keys]
        return ContentProtectionSpecificBox(version=1, flags=0,
                                            system_id=self.RAW_PSSH_SYSTEM_ID,
                                            key_ids=keys,
                                            data=None
                                            )
