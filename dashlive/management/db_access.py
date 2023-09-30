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
from pathlib import Path

from .info import KeyInfo, StreamInfo

class DatabaseAccess(ABC):
    """
    Defines functions required to access database
    """

    @abstractmethod
    def login(self) -> bool:
        ...

    @abstractmethod
    def fetch_media_info(self, with_details: bool = False) -> bool:
        ...

    @abstractmethod
    def get_streams(self) -> list[StreamInfo]:
        ...

    @abstractmethod
    def get_stream_info(self, directory: str) -> StreamInfo | None:
        ...

    @abstractmethod
    def get_keys(self) -> dict[str, KeyInfo]:
        ...

    @abstractmethod
    def add_key(self, kid: str, computed: bool,
                key: str | None = None, alg: str | None = None) -> bool:
        ...

    @abstractmethod
    def add_stream(self, directory: str, title: str, marlin_la_url: str = '',
                   playready_la_url: str = '', **kwargs) -> StreamInfo | None:
        ...

    @abstractmethod
    def upload_file(self, stream: StreamInfo, name: Path) -> bool:
        ...

    @abstractmethod
    def index_file(self, stream: StreamInfo, name: Path) -> bool:
        ...

    @abstractmethod
    def set_timing_ref(self, stream: StreamInfo, timing_ref: str) -> bool:
        ...
