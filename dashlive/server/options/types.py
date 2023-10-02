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

from dataclasses import dataclass, field
from enum import IntFlag, auto
from typing import AbstractSet, NamedTuple, Union

from dashlive.utils.json_object import JsonObject

class OptionUsage(IntFlag):
    MANIFEST = auto()
    VIDEO = auto()
    AUDIO = auto()
    TEXT = auto()
    TIME = auto()
    HTML = auto()

    @classmethod
    def from_string(cls, value: str) -> "OptionUsage":
        return cls.__members__[value.upper()]

    @classmethod
    def to_string_set(cls, value: Union[int, "OptionUsage"]) -> set[str]:
        """
        Create a set of strings for all items in this flag
        """
        rv: set[str] = set()
        if isinstance(value, OptionUsage):
            value = value.value
        for name, flag in OptionUsage.__members__.items():
            if value & flag.value:
                rv.add(name.lower())
        return rv


class CgiOptionChoice(NamedTuple):
    description: str
    value: str | bool | int


@dataclass(frozen=True, slots=True)
class CgiOption:
    """
    Container class for one CGI option
    """
    name: str
    title: str
    options: list[CgiOptionChoice]
    syntax: str = ''
    usage: set[str] = field(default_factory=lambda: set())
    html: str = ''
    hidden: bool = False

    def toJSON(self, pure: bool = False,
               exclude: AbstractSet | None = None) -> JsonObject:
        rv = {
            'hidden': self.hidden,
            'html': self.html,
            'name': self.name,
            'options': self.options,
            'syntax': self.syntax,
            'title': self.title,
        }
        if exclude is None:
            return rv
        for k in rv.keys():
            if k in exclude:
                del rv[k]
        return rv
