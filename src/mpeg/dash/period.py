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

from objects import ListOf, ObjectWithFields
from adaptation_set import AdaptationSet

class Period(ObjectWithFields):
    OBJECT_FIELDS = {
        'adaptationSets': ListOf(AdaptationSet),
        'start': datetime.timedelta,
    }
    DEFAULT_VALUES = {
        'start': datetime.timedelta(0),
        'id': 'p0',
    }

    def __init__(self, **kwargs):
        """
        Required kwargs:
        mode
        contentType
        """
        super(AdaptationSet, self).__init__(**kwargs)
        defaults = {
            'adaptationSets': [],
            'event_streams': [],
        }
        self.apply_defaults(defaults)
