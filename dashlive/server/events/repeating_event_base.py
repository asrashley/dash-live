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

from abc import abstractmethod
from typing import TYPE_CHECKING

from dashlive.mpeg.dash.event_stream import EventStream
from dashlive.mpeg.mp4 import EventMessageBox, MovieFragmentBox

from .base import EventBase

if TYPE_CHECKING:
    from dashlive.mpeg.dash.representation import Representation

class RepeatingEventBase(EventBase):
    """
    A base class for events that repeat at a fixed interval
    """

    def create_manifest_context(self, context: dict) -> dict:
        stream = EventStream(
            schemeIdUri=self.schemeIdUri,
            value=self.value,
            timescale=self.timescale,
            inband=self.inband)

        if not self.inband and self.count > 0:
            presentation_time = self.start
            for idx in range(self.count):
                data = self.get_manifest_event_payload(idx, presentation_time)
                stream.events.append({
                    'data': data,
                    'duration': self.duration,
                    'id': idx,
                    'presentationTime': presentation_time
                })
                presentation_time += self.interval
        return stream

    @abstractmethod
    def get_manifest_event_payload(self, index, presentation_time) -> str:
        return ""

    def create_emsg_boxes(self,
                          segment_num: int,
                          mod_segment: int,
                          moof: MovieFragmentBox,
                          representation: "Representation",
                          **kwargs) -> list[EventMessageBox]:
        if not self.inband:
            return []
        # start and end time of the fragment (representation timebase)
        seg_start: int = moof['traf.tfdt'].base_media_decode_time
        seg_end: int = seg_start + representation.segments[mod_segment].duration

        # convert seg_start and seg_end to event timebase
        seg_start: int = (seg_start * self.timescale) // representation.timescale
        seg_end: int = (seg_end * self.timescale) // representation.timescale

        # print('seg start={} end={} duration={}'.format(
        #    seg_start, seg_end, seg_end - seg_start))

        # presentation_time is using event timebase
        presentation_time: int = self.start

        if presentation_time >= seg_end:
            return []

        if self.count > 0:
            # ev_end is using event timescale
            ev_end = presentation_time + (self.count * self.interval)
            if ev_end < seg_start:
                return []

        event_id: int = 0
        if seg_start > presentation_time:
            event_id = ((seg_start - presentation_time) //
                        self.interval)
        assert (event_id >= 0)
        presentation_time += event_id * self.interval
        retval: list[EventMessageBox] = []
        while presentation_time < seg_end:
            if presentation_time < seg_start:
                event_id += 1
                presentation_time += self.interval
                continue
            assert (presentation_time >= seg_start)
            data: bytes = self.get_emsg_event_payload(
                event_id, presentation_time)
            kwargs = {
                'version': self.version,
                'flags': 0,
                'scheme_id_uri': self.schemeIdUri,
                'timescale': self.timescale,
                'event_duration': self.duration,
                'event_id': event_id,
                'value': self.value,
                'data': data,
            }
            if kwargs['version'] == 0:
                time_delta: int = presentation_time - seg_start
                kwargs['presentation_time_delta'] = time_delta
            else:
                kwargs['presentation_time'] = presentation_time
            retval.append(EventMessageBox(**kwargs))
            event_id += 1
            if self.count > 0 and event_id >= self.count:
                break
            presentation_time += self.interval
        return retval

    @abstractmethod
    def get_emsg_event_payload(self, event_id: int, presentation_time: int) -> bytes:
        ...
