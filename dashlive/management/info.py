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
from dataclasses import dataclass, InitVar
from typing import AbstractSet

from dashlive.utils.json_object import JsonObject

@dataclass(slots=True)
class UserInfo:
    email: str
    groups: list[str]
    last_login: str
    pk: int
    username: str

    def to_dict(self) -> JsonObject:
        return {
            'email': self.email,
            'groups': str(self.groups),
            'last_login': self.last_login,
            'pk': self.pk,
            'username': self.username
        }

@dataclass(slots=True)
class BlobInfo:
    content_type: str
    created: str
    filename: str
    pk: int
    sha1_hash: str
    size: int
    auto_delete: bool

    def to_dict(self) -> JsonObject:
        return {
            'auto_delete': True,
            'content_type': self.content_type,
            'created': self.created,
            'filename': self.filename,
            'pk': self.pk,
            'sha1_hash': self.sha1_hash,
            'size': self.size
        }

class MediaFileInfo:
    def __init__(self, bitrate: int, content_type: str, encrypted: bool,
                 pk: int, blob: JsonObject | None = None,
                 **kwargs) -> None:
        self.bitrate = bitrate
        self.content_type = content_type
        self.encrypted = encrypted
        self.pk = pk
        if blob:
            self.blob = BlobInfo(**blob)
        else:
            self.blob = None

    def to_dict(self) -> JsonObject:
        result = {
            'bitrate': self.bitrate,
            'blob': self.blob,
            'content_type': self.content_type,
            'encrypted': self.encrypted,
            'pk': self.pk
        }
        if result['blob']:
            result['blob'] = result['blob'].to_dict()
        return result


@dataclass(slots=True, kw_only=True)
class StreamTimingRef:
    media_name: str
    media_duration: int  # in timescale units
    segment_duration: int  # in timescale units
    num_media_segments: int
    timescale: int  # ticks per second

@dataclass(slots=True, kw_only=True)
class StreamInfo:
    pk: int
    title: str
    directory: str
    blob: JsonObject | None = None
    marlin_la_url: str | None = None
    playready_la_url: str | None = None
    timing_ref: StreamTimingRef | None = None
    media_files: list[JsonObject] | dict[str, MediaFileInfo] | None = None
    keys: list[JsonObject] | None = None
    upload_url: str | None = None
    csrf_tokens: JsonObject | None = None
    csrf_token: InitVar[str | None] = None
    id: InitVar[str | None] = None

    def __post_init__(self, *args):
        if isinstance(self.timing_ref, dict):
            self.timing_ref = StreamTimingRef(**self.timing_ref)
        media_files = {}
        if self.media_files is not None:
            for mf in self.media_files:
                if isinstance(mf, dict):
                    media_files[mf['name']] = MediaFileInfo(**mf)
        self.media_files = media_files

    def to_dict(self, only: AbstractSet[str] | None = None) -> JsonObject:
        result = {}
        for name in {'directory', 'title', 'marlin_la_url', 'playready_la_url', 'timing_ref'}:
            if only is None or name in only:
                result[name] = getattr(self, name)
        if only is None or 'files' in only:
            result['files'] = [mf.to_dict() for mf in self.media_files.values()]
        return result
