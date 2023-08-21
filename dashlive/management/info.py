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
from dataclasses import dataclass
from typing import AbstractSet

from dashlive.utils.json_object import JsonObject

@dataclass
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

@dataclass
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

class StreamInfo:
    def __init__(self, pk: int, title: str, directory: str,
                 blob: JsonObject | None = None,
                 marlin_la_url: str | None = None,
                 playready_la_url: str | None = None,
                 media_files: list[JsonObject] | None = None,
                 keys: list[JsonObject] | None = None,
                 upload_url: str | None = None,
                 csrf_tokens: JsonObject | None = None,
                 **kwargs) -> None:
        self.pk = pk
        self.title = title
        self.directory = directory
        self.blob = blob
        self.marlin_la_url = marlin_la_url
        self.playready_la_url = playready_la_url
        self.upload_url = upload_url
        self.csrf_tokens = csrf_tokens
        self.media_files: dict[str, MediaFileInfo] = {}
        if media_files is not None:
            for mf in media_files:
                if isinstance(mf, dict):
                    self.media_files[mf['name']] = MediaFileInfo(**mf)

    def to_dict(self, only: AbstractSet[str] | None = None) -> JsonObject:
        result = {}
        for name in {'directory', 'title', 'marlin_la_url', 'playready_la_url'}:
            if only is None or name in only:
                result[name] = getattr(self, name)

        if only is None or 'files' in only:
            result['files'] = [mf.to_dict() for mf in self.media_files.values()]
        return result
