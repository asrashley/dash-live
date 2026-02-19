#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from typing import TYPE_CHECKING, ClassVar

from dashlive.server.options.dash_option import DashOption

from .base import EventBase
from .ping_pong import PingPongEvents
from .scte35_events import Scte35Events

if TYPE_CHECKING:
    from dashlive.server.options.container import OptionsContainer

class EventFactory:
    EVENT_TYPES: ClassVar[dict[str, EventBase]] = {
        PingPongEvents.PREFIX: PingPongEvents,
        Scte35Events.PREFIX: Scte35Events,
    }

    @classmethod
    def create_event_generators(cls, options: "OptionsContainer") -> list[EventBase]:
        retval = []
        for name in options.eventTypes:
            try:
                EventClazz = cls.EVENT_TYPES[name]
            except KeyError as err:
                print(f'Unknown event class "{name}": {err}')
                continue
            args = getattr(options, EventClazz.PREFIX).toJSON()
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
