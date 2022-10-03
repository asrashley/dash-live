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

import urllib

from drm.base import DrmBase


class Marlin(DrmBase):
    MPD_SYSTEM_ID = '5e629af5-38da-4063-8977-97ffbd9902d4'

    def generate_manifest_context(self, stream, keys, cgi_params, la_url=None, locations=None):
        if la_url is None:
            la_url = cgi_params.get('marlin_la_url')
            if la_url is not None:
                la_url = urllib.unquote_plus(la_url)
            else:
                la_url = stream.marlin_la_url
        return {
            'MarlinContentIds': True,
            'laurl': la_url,
            'scheme_id': self.dash_scheme_id(),
        }

    def generate_pssh(self, representation, keys):
        raise RuntimeError('generate_pssh has not been implemented for Marlin')

    def dash_scheme_id(self):
        """
        Returns the DASH schemeIdUri for Marlin
        """
        return "urn:uuid:{0}".format(self.MPD_SYSTEM_ID)

    @classmethod
    def is_supported_scheme_id(cls, uri):
        uri = uri.lower()
        if not uri.startswith("urn:uuid:"):
            return False
        return uri[9:] == cls.MPD_SYSTEM_ID
