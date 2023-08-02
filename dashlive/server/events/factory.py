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

from builtins import object
from typing import List

from flask import Request

from .base import EventBase
from .ping_pong import PingPongEvents
from .scte35_events import Scte35Events

class EventFactory(object):
    EVENT_TYPES = {
        PingPongEvents.PREFIX: PingPongEvents,
        Scte35Events.PREFIX: Scte35Events,
    }

    @classmethod
    def create_event_generators(cls, request: Request) -> List[EventBase]:
        names = request.args.get("events", "").lower()
        if not names:
            return []
        retval = []
        for name in names.split(','):
            if name == 'none':
                continue
            try:
                EventClazz = cls.EVENT_TYPES[name]
            except KeyError as err:
                print(f'Unknown event class "{name}": {err}')
                continue
            retval.append(EventClazz(request))
        return retval
