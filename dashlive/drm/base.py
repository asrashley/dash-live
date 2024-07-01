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

from abc import ABC, abstractmethod
from typing import AbstractSet, NamedTuple, Protocol

from dashlive.mpeg.mp4 import BoxWithChildren, ContentProtectionSpecificBox
from dashlive.server.models import Stream
from dashlive.server.options.container import OptionsContainer

from .key_tuple import KeyTuple

class CustomAttribute(NamedTuple):
    tag: str
    value: str
    attributes: dict[str, str] | None


class CreateDrmData(Protocol):
    def __call__(
            self,
            default_kid: str,
            custom_attributes: list[CustomAttribute] | None = None) -> bytes:
        ...


class CreatePsshBox(Protocol):
    def __call__(
            self,
            default_kid: str,
            custom_attributes: list[CustomAttribute] | None = None) -> ContentProtectionSpecificBox:
        ...


class ManifestContext(NamedTuple):
    laurl: str
    scheme_id: str
    version: float
    cenc: CreatePsshBox | None
    moov: CreatePsshBox | None
    pro: CreateDrmData | None


class DrmBase(ABC):
    """
    Base class for all DRM implementations
    """

    @abstractmethod
    def dash_scheme_id(self) -> str:
        raise RuntimeError('dash_scheme_id has not been implemented')

    @abstractmethod
    def generate_manifest_context(self, stream: Stream,
                                  keys: dict[str, KeyTuple],
                                  options: OptionsContainer,
                                  la_url: str | None = None,
                                  https_request: bool = False,
                                  locations: AbstractSet[str] | None = None) -> ManifestContext:
        raise RuntimeError('generate_manifest_context has not been implemented')

    def update_traf_if_required(self, options: OptionsContainer,
                                traf: BoxWithChildren) -> bool:
        """
        Hook to allow a DRM system to insert / modify boxes within the "traf"
        box.
        :returns: True if the traf has been modified
        """
        return False
