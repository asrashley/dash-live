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

from dashlive.utils.list_of import ListOf
from dashlive.utils.object_with_fields import ObjectWithFields

from .adaptation_set import AdaptationSet

class Period(ObjectWithFields):
    """
    Class used to hold data about one Period
    """
    id: str
    adaptationSets: list[AdaptationSet]
    start: datetime.timedelta

    OBJECT_FIELDS: ClassVar[dict[str, Any]] = {
        'adaptationSets': ListOf(AdaptationSet),
        'start': datetime.timedelta,
    }
    DEFAULT_VALUES: ClassVar[dict[str, Any]] = {
        'start': datetime.timedelta(0),
        'id': 'p0',
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        defaults = {
            'adaptationSets': [],
            'event_streams': [],
        }
        self.apply_defaults(defaults)

    def key_ids(self):
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
