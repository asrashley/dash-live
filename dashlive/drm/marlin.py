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

from dashlive.mpeg.mp4 import ContentProtectionSpecificBox
from dashlive.server.options.container import OptionsContainer

from .base import DrmBase

class Marlin(DrmBase):
    MPD_SYSTEM_ID = '5e629af5-38da-4063-8977-97ffbd9902d4'

    def generate_manifest_context(self, stream, keys,
                                  options: OptionsContainer,
                                  la_url: str | None = None,
                                  https_request: bool = False,
                                  locations: str | None = None) -> dict:
        if la_url is None:
            la_url = options.licenseUrl
            if la_url is None:
                la_url = stream.marlin_la_url
        return {
            'MarlinContentIds': True,
            'laurl': la_url,
            'scheme_id': self.dash_scheme_id(),
        }

    def generate_pssh(self, representation, keys) -> ContentProtectionSpecificBox:
        raise RuntimeError('generate_pssh has not been implemented for Marlin')

    def dash_scheme_id(self) -> str:
        """
        Returns the DASH schemeIdUri for Marlin
        """
        return f'urn:uuid:{self.MPD_SYSTEM_ID}'

    @classmethod
    def is_supported_scheme_id(cls, uri: str) -> bool:
        uri = uri.lower()
        if not uri.startswith("urn:uuid:"):
            return False
        return uri[9:] == cls.MPD_SYSTEM_ID
