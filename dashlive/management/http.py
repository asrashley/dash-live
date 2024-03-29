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
from typing import Protocol

from dashlive.utils.json_object import JsonObject

class HttpResponse(Protocol):
    status_code: int
    headers: dict
    text: str

    def json(self) -> JsonObject:
        """parses body as a JSON object"""


class HttpSession(Protocol):
    """
    Interface that describes the HTTP requests used by PopulateDatabase
    """
    def get(self, url: str, params: dict | None = None,
            headers: dict | None = None) -> HttpResponse:
        """Make a GET request"""

    def post(self, url: str,
             data: bytes | None = None,
             files: list[tuple] | None = None,
             params: JsonObject | None = None,
             json: JsonObject | None = None) -> HttpResponse:
        """Make a POST request"""

    def put(self, url: str,
            params: dict | None = None,
            json: JsonObject | None = None) -> HttpResponse:
        """Make a PUT request"""
