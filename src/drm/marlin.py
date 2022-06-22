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

from drm.base import DrmBase


class Marlin(DrmBase):
    MPD_SYSTEM_ID = '5e629af5-38da-4063-8977-97ffbd9902d4'

    def generate_pssh(self, representation, keys):
        raise RuntimeError('generate_pssh has not been implemented for Marlin')

    def dash_scheme_id(self):
        """
        Returns the DASH schemeIdUri for Marlin
        """
        return "urn:uuid:{0}".format(self.MPD_SYSTEM_ID)

    @classmethod
    def is_supported_scheme_id(cls, uri):
        if not uri.startswith("urn:uuid:"):
            return False
        return uri[9:].lower() == cls.SYSTEM_ID
