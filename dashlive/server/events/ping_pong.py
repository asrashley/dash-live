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

from .repeating_event_base import RepeatingEventBase

class PingPongEvents(RepeatingEventBase):
    """
    The PingPong event scheme alternates payloads of 'ping' and 'pong'
    """
    schemeIdUri = r'urn:dash-live:pingpong:2022'

    PREFIX = "ping"

    def __init__(self, request):
        super(PingPongEvents, self).__init__(self.PREFIX + "_", request)

    def get_manifest_event_payload(self, event_id, presentation_time) -> str:
        if (event_id & 1) == 0:
            return 'ping'
        return 'pong'

    def get_emsg_event_payload(self, event_id, presentation_time) -> str:
        data = 'ping' if (event_id & 1) == 0 else 'pong'
        return data
