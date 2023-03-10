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

from abc import ABCMeta, abstractmethod


class DrmBase(object):
    """
    Base class for all DRM implementations
    """
    __metaclass__ = ABCMeta

    def __init__(self, templates):
        self.templates = templates

    @abstractmethod
    def dash_scheme_id(self):
        raise RuntimeError('dash_scheme_id has not been implemented')

    @abstractmethod
    def generate_manifest_context(self, stream, keys, cgi_params, la_url=None, locations=None):
        raise RuntimeError('generate_manifest_context has not been implemented')

    def update_traf_if_required(self, cgi_params, traf):
        """
        Hook to allow a DRM system to insert / modify boxes within the "traf"
        box.
        :returns: True if the traf has been modified
        """
        return False

    @abstractmethod
    def generate_pssh(self, representation, keys):
        raise RuntimeError('generate_pssh has not been implemented')
