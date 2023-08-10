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

from typing import ClassVar

from dashlive.server.options.dash_option import DashOption
from dashlive.server.options.container import OptionsContainer

from .base import EventBase
from .ping_pong import PingPongEvents
from .scte35_events import Scte35Events

class EventFactory:
    EVENT_TYPES: ClassVar[dict[str, EventBase]] = {
        PingPongEvents.PREFIX: PingPongEvents,
        Scte35Events.PREFIX: Scte35Events,
    }

    @classmethod
    def create_event_generators(cls, options: OptionsContainer) -> list[EventBase]:
        retval = []
        for name in options.eventTypes:
            try:
                EventClazz = cls.EVENT_TYPES[name]
            except KeyError as err:
                print(f'Unknown event class "{name}": {err}')
                continue
            args = options[EventClazz.PREFIX].toJSON(exclude={'_type'})
            retval.append(EventClazz(**args))
        return retval

    @classmethod
    def get_dash_options(cls) -> list[DashOption]:
        """
        Get a list of all event DASH options
        """
        result: list[DashOption] = []
        for ev_cls in cls.EVENT_TYPES.values():
            result += ev_cls.get_dash_options()
        return result
