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
from typing import Callable, Generic, TypeVar

T = TypeVar('T')

EventCallback = Callable[[str, T], None]

class EventBus(Generic[T]):
    listeners: dict[str, list[EventCallback]]

    def __init__(self) -> None:
        self.listeners = {}

    def on(self, name: str, listener: EventCallback) -> None:
        # print('eventlistener.on', name)
        try:
            ev_listeners: list[EventCallback] = self.listeners[name]
        except KeyError:
            ev_listeners = []
        ev_listeners.append(listener)
        self.listeners[name] = ev_listeners

    def off(self, name: str, listener: EventCallback) -> None:
        # print('eventlistener.off', name)
        try:
            self.listeners[name] = list(
                filter(lambda item: item != listener, self.listeners[name]))
        except KeyError:
            pass

    def trigger(self, name: str, payload: T) -> None:
        # print('eventlistener.trigger', name)
        try:
            ev_listeners = self.listeners[name]
        except KeyError:
            # print(f'No {name} listeners')
            return
        for cb in ev_listeners:
            try:
                cb(name, payload)
            except Exception as err:
                print(f'Event listener error: {err}')
