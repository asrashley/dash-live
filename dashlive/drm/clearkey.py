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
import urllib.parse
from typing import AbstractSet

import flask

from dashlive.mpeg.mp4 import ContentProtectionSpecificBox
from dashlive.server.options.container import OptionsContainer
from dashlive.server.models import Stream

from .base import CreateDrmData, DrmBase, DrmManifestContext
from .keymaterial import KeyMaterial
from .key_tuple import KeyTuple
from .system import DrmSystem

class ClearKey(DrmBase):
    MPD_SYSTEM_ID = "e2719d58-a985-b3c9-781a-b030af78d30e"
    PSSH_SYSTEM_ID = "1077efec-c0b2-4d02-ace3-3c1e52e2fb4b"
    RAW_PSSH_SYSTEM_ID = binascii.a2b_hex(PSSH_SYSTEM_ID.replace('-', ''))

    def dash_scheme_id(self):
        return f"urn:uuid:{self.MPD_SYSTEM_ID}"

    def generate_manifest_context(
            self, stream: Stream,
            keys: dict[str, KeyTuple],
            options: OptionsContainer,
            la_url: str | None = None,
            https_request: bool = False,
            locations: AbstractSet[str] | None = None) -> DrmManifestContext:
        if locations is None:
            locations = {'cenc', 'moov'}
        if la_url is None:
            la_url = urllib.parse.urljoin(
                flask.request.host_url, flask.url_for('clearkey'))
            if https_request:
                la_url = la_url.replace('http://', 'https://')

        def generate_pssh_box(default_kid: str, cattr: list | None = None) -> bytes:
            return self.generate_pssh(default_kid, keys)

        cenc: CreateDrmData | None = None
        moov: CreateDrmData | None = None
        if 'cenc' in locations:
            cenc = generate_pssh_box
        if 'moov' in locations:
            moov = generate_pssh_box
        return DrmManifestContext(
            system=DrmSystem.CLEARKEY,
            scheme_id=self.dash_scheme_id(),
            laurl=la_url,
            cenc=cenc,
            moov=moov,
            pro=None,
            version=0,
        )

    def generate_pssh(self, default_kid: str, keys: dict[str, KeyTuple]) -> ContentProtectionSpecificBox:
        """Generate a Clearkey PSSH box"""
        # see https://www.w3.org/TR/eme-initdata-cenc/
        if isinstance(keys, dict):
            keys = list(keys.keys())
        keys = [KeyMaterial(k).raw for k in keys]
        return ContentProtectionSpecificBox(
            version=1,
            flags=0,
            system_id=self.RAW_PSSH_SYSTEM_ID,
            key_ids=keys,
            data=None)
