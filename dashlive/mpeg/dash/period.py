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

import datetime
from typing import Any, ClassVar
import urllib.parse

from dashlive.drm.keymaterial import KeyMaterial
from dashlive.mpeg.dash.event_stream import EventStream
from dashlive.server.options.container import OptionsContainer
import flask

from dashlive.utils.list_of import ListOf
from dashlive.utils.object_with_fields import ObjectWithFields

from .adaptation_set import AdaptationSet
from .timing import DashTiming

class Period(ObjectWithFields):
    """
    Class used to hold data about one Period
    """
    id: str
    adaptationSets: list[AdaptationSet]
    event_streams: list[EventStream]
    start: datetime.timedelta
    duration: datetime.timedelta | None = None
    mpdDuration: datetime.timedelta | None = None  # value used in manifest
    time_offset: datetime.timedelta

    OBJECT_FIELDS: ClassVar[dict[str, Any]] = {
        'adaptationSets': ListOf(AdaptationSet),
        'start': datetime.timedelta,
    }
    DEFAULT_VALUES: ClassVar[dict[str, Any]] = {
        'start': datetime.timedelta(0),
        'id': 'p0',
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        defaults = {
            'adaptationSets': [],
            'event_streams': [],
            'start': datetime.timedelta(),
            'time_offset': datetime.timedelta(),
        }
        self.apply_defaults(defaults)

    def key_ids(self) -> set[KeyMaterial]:
        kids = set()
        for adp in self.adaptationSets:
            kids.update(adp.key_ids())
        return kids

    def video_track(self) -> AdaptationSet:
        for adp in self.adaptationSets:
            if adp.content_type == 'video':
                return adp
        raise AttributeError('Failed to find a video AdaptationSet')

    def audio_tracks(self) -> list[AdaptationSet]:
        rv: list[AdaptationSet] = []
        for adp in self.adaptationSets:
            if adp.content_type == 'audio':
                rv.append(adp)
        return rv

    @property
    def maxSegmentDuration(self) -> float:
        if not self.adaptationSets:
            return 1
        return max([a.maxSegmentDuration for a in self.adaptationSets])

    def finish_setup(self,
                     timing: DashTiming | None,
                     base_url: str,
                     options: OptionsContainer) -> None:
        if options.useBaseUrls:
            self.baseURL = urllib.parse.urljoin(flask.request.host_url, base_url)
        if options.mode == 'live' and not options.forcePeriodDurations:
            self.mpdDuration = None
        else:
            self.mpdDuration = self.duration

        for adp in self.adaptationSets:
            if options.mode == 'odvod':
                for rep in adp.representations:
                    rep.baseURL = f"{rep.id}.{adp.fileSuffix}"
                    if not options.useBaseUrls:
                        rep.baseURL = f"{base_url}{rep.baseURL}"
            if not options.useBaseUrls:
                if options.mode != 'odvod':
                    adp.initURL = f"{base_url}{adp.initURL}"
                adp.mediaURL = f"{base_url}{adp.mediaURL}"
            if timing:
                adp.set_dash_timing(timing, self.start, self.time_offset, self.duration)
