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
import argparse
import json
import logging
from pathlib import Path
import time
from typing import AbstractSet, Dict, List, Optional, Protocol, Tuple
import urllib

from dashlive.utils.json_object import JsonObject

class BlobInfo:
    def __init__(self, content_type: str, created: str, filename: str,
                 pk: int, sha1_hash: str, size: int, **kwargs) -> None:
        self.content_type = content_type
        self.created = created
        self.filename = filename
        self.pk = pk
        self.sha1_hash = sha1_hash
        self.size = size

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
                 pk: int, blob: Optional[BlobInfo] = None,
                 **kwargs) -> None:
        self.bitrate = bitrate
        self.content_type = content_type
        self.encrypted = encrypted
        self.pk = pk
        self.blob = blob

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
                 blob: Optional[JsonObject] = None,
                 marlin_la_url: Optional[str] = None,
                 playready_la_url: Optional[str] = None,
                 media_files: Optional[List[JsonObject]] = None,
                 keys: Optional[List[JsonObject]] = None,
                 upload_url: Optional[str] = None,
                 csrf_tokens: Optional[JsonObject] = None,
                 **kwargs) -> None:
        self.pk = pk
        self.title = title
        self.directory = directory
        self.blob = blob
        self.marlin_la_url = marlin_la_url
        self.playready_la_url = playready_la_url
        self.upload_url = upload_url
        self.csrf_tokens = csrf_tokens
        self.media_files: Dict[str, MediaFileInfo] = {}
        if media_files is not None:
            for mf in media_files:
                if isinstance(mf, dict):
                    self.media_files[mf['name']] = MediaFileInfo(**mf)

    def to_dict(self, only: Optional[AbstractSet[str]] = None) -> JsonObject:
        result = {}
        for name in {'directory', 'title', 'marlin_la_url', 'playready_la_url'}:
            if only is None or name in only:
                result[name] = getattr(self, name)
        
        if only is None or 'files' in only:
            result['files'] = [mf.to_dict() for mf in self.media_files.values()]
        return result
