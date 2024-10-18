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

import time
from dataclasses import dataclass
from typing import Any, ClassVar, Set

from dashlive.utils.objects import dict_to_cgi_params
from dashlive.utils.list_of import ListOf
from dashlive.utils.object_with_fields import ObjectWithFields
from dashlive.drm.base import DrmBase
from dashlive.drm.keymaterial import KeyMaterial

from .event_stream import EventStream
from .mime_types import content_type_to_mime_type, content_type_file_suffix
from .representation import Representation
from .timing import DashTiming

@dataclass(kw_only=True, slots=True)
class ContentComponent:
    id: int
    content_type: str


class AdaptationSet(ObjectWithFields):
    _NEXT_ID: ClassVar[int | None] = None
    OBJECT_FIELDS: ClassVar[dict[str, Any]] = {
        'event_streams': ListOf(EventStream),
        'representations': ListOf(Representation),
        'drm': DrmBase | None,
    }
    DEFAULT_VALUES: ClassVar[dict[str, Any]] = {
        'timescale': 1,
        'segmentAlignment': True,
        'segment_timeline': False,
        'drm': None,
        'default_kid': None,
        'lang': None,
    }

    def __init__(self, **kwargs) -> None:
        """
        Required kwargs:
        mode
        content_type
        """
        super().__init__(**kwargs)
        defaults = {
            'id': AdaptationSet.get_next_id(),
            'representations': [],
            'event_streams': [],
            'mimeType': content_type_to_mime_type(
                self.content_type, kwargs.get('codecs', None)),
            'fileSuffix': content_type_file_suffix(self.content_type),
        }
        if self.content_type == 'audio':
            defaults['lang'] = 'und'
            defaults['role'] = 'main'
            defaults['numChannels'] = 2
        elif self.content_type == 'video':
            defaults['startWithSAP'] = 1
            defaults['par'] = "16:9"
        elif self.content_type == 'text':
            defaults['lang'] = 'und'
            defaults['role'] = 'subtitle'
        suffix: str = defaults['fileSuffix']
        if self.mode == 'odvod':
            defaults['mediaURL'] = f'$RepresentationID$.{suffix}'
        else:
            defaults['initURL'] = f'$RepresentationID$/init.{suffix}'
            if self.segment_timeline:
                defaults['mediaURL'] = f'$RepresentationID$/time/$Time$.{suffix}'
            else:
                defaults['mediaURL'] = f'$RepresentationID$/$Number$.{suffix}'
        self.apply_defaults(defaults)
        if self.encrypted and self.default_kid is None:
            for rp in self.representations:
                if rp.default_kid is not None:
                    self.default_kid = rp.default_kid
                    break

    @classmethod
    def get_next_id(cls) -> int:
        if cls._NEXT_ID is None:
            cls._NEXT_ID = hash(time.time())
        rv = cls._NEXT_ID
        cls._NEXT_ID += 1
        return rv

    @property
    def contentComponent(self) -> ContentComponent | None:
        if self.representations:
            return ContentComponent(
                id=self.representations[0].track_id,
                content_type=self.content_type)
        return None

    @property
    def start_number(self) -> int:
        if self.representations:
            return self.representations[0].start_number
        return 1

    @property
    def segment_duration(self) -> int:
        if self.representations:
            return self.representations[0].segment_duration
        return 0

    @property
    def encrypted(self) -> bool:
        for rep in self.representations:
            if rep.encrypted:
                return True
        return False

    def key_ids(self) -> Set[KeyMaterial]:
        kids: Set[KeyMaterial] = set()
        for rep in self.representations:
            if rep.encrypted:
                kids.update(rep.kids)
        return kids

    def append_cgi_params(self, params: dict[str, str]) -> None:
        if not params:
            return
        qs = dict_to_cgi_params(params)
        self.mediaURL += qs
        if self.mode != 'odvod':
            self.initURL += qs

    @property
    def maxSegmentDuration(self) -> float:
        if self.timescale < 1 or not self.representations:
            return 1
        return max([
            a.segment_duration for a in self.representations
        ]) / float(self.timescale)

    @property
    def minBitrate(self) -> int:
        if not self.representations:
            return 0
        return min([a.bitrate for a in self.representations])

    @property
    def maxBitrate(self) -> int:
        if not self.representations:
            return 0
        return max([a.bitrate for a in self.representations])

    def compute_av_values(self) -> None:
        if not self.representations:
            return
        self.timescale = self.representations[0].timescale
        self.presentationTimeOffset = int(
            (self.start_number - 1) * self.representations[0].segment_duration)

        if self.content_type in {'audio', 'text'}:
            for rep in self.representations:
                if rep.lang:
                    self.lang = rep.lang
                if self.content_type == 'audio':
                    self.sampleRate = rep.sampleRate
                    self.numChannels = rep.numChannels
        elif self.content_type == 'video':
            self.minWidth = min(
                [a.width for a in self.representations])
            self.minHeight = min(
                [a.height for a in self.representations])
            self.maxWidth = max(
                [a.width for a in self.representations])
            self.maxHeight = max(
                [a.height for a in self.representations])
            self.maxFrameRate = max(
                [a.frameRate for a in self.representations])

    def set_dash_timing(self, timing: DashTiming) -> None:
        for rep in self.representations:
            rep.set_dash_timing(timing)
