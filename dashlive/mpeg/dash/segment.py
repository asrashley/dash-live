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
from dataclasses import dataclass

from typing import AbstractSet

from dashlive.utils.json_object import JsonObject

@dataclass(slots=True, kw_only=True)
class Segment:
    pos: int
    size: int
    duration: int | None = None
    start: int | None = None

    def toJSON(self, pure: bool = False,
               exclude: AbstractSet | None = None) -> JsonObject:
        rv = {
            "pos": self.pos,
            "size": self.size,
        }
        if self.duration:
            rv["duration"] = self.duration
        if exclude is None:
            return rv
        for k in rv.keys():
            if k in exclude:
                del rv[k]
        return rv

    def __repr__(self) -> str:
        if self.duration:
            return f'({self.pos:d},{self.size:d},{self.duration:d})'
        return f'({self.pos:d},{self.size:d})'
