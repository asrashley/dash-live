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

from abc import ABCMeta, abstractmethod
import copy
import datetime

from mpeg.dash.event_stream import EventStream
from mpeg import mp4, MPEG_TIMEBASE
from scte35 import descriptors
from scte35.binarysignal import BinarySignal, SapType
from scte35.splice_insert import SpliceInsert
from utils.date_time import from_isodatetime

class EventFactory(object):
    EVENT_TYPES = {
    }

    @classmethod
    def create_event_generators(cls, request):
        names = request.params.get("events", "").lower()
        if not names:
            return []
        retval = []
        for name in names.split(','):
            try:
                EventClazz = cls.EVENT_TYPES[name]
            except KeyError as err:
                print(err)
                continue
            retval.append(EventClazz(request))
        return retval

class EventBase(object):
    __metaclass__ = ABCMeta

    PARAMS = {
        'count': 0,
        'duration': 200,
        'inband': True,
        'interval': 1000,
        'start': 0,
        'timescale': 100,
        'value': '0',
        'version': 0,
    }

    def __init__(self, prefix, request, extra_params=None):
        all_params = copy.deepcopy(self.PARAMS)
        if extra_params is not None:
            all_params.update(extra_params)
        self.prefix = prefix
        self.params = set()
        for key, dflt in all_params.iteritems():
            value = request.params.get(prefix + key, dflt)
            if isinstance(dflt, bool):
                if isinstance(value, basestring):
                    value = value.lower() in {'true', 'yes', '1'}
                elif isinstance(value, (int, long)):
                    value = (value == 1)
            elif isinstance(dflt, int):
                value = int(value)
            elif isinstance(dflt, long):
                value = long(value)
            elif isinstance(dflt, (
                    datetime.date, datetime.datetime, datetime.time,
                    datetime.timedelta)):
                value = from_isodatetime(value)
            setattr(self, key, value)
            self.params.add(key)

    def cgi_parameters(self):
        """
        Get all parameters for this event generator as a dictionary
        """
        retval = {}
        for key in self.params:
            value = getattr(self, key)
            retval['{0:s}{1:s}'.format(self.prefix, key)] = value
        return retval

    @abstractmethod
    def create_manifest_context(self, context):
        return {}

    @abstractmethod
    def create_emsg_boxes(self, **kwargs):
        return None

class RepeatingEventBase(EventBase):
    """
    A base class for events that repeat at a fixed interval
    """

    def create_manifest_context(self, context, templates):
        stream = EventStream(
            schemeIdUri=self.schemeIdUri,
            value=self.value,
            timescale=self.timescale,
            inband=self.inband)

        if not self.inband and self.count > 0:
            presentation_time = self.start
            for idx in range(self.count):
                data = self.get_manifest_event_payload(templates, idx, presentation_time)
                stream.events.append({
                    'data': data,
                    'duration': self.duration,
                    'id': idx,
                    'presentationTime': presentation_time
                })
                presentation_time += self.interval
        return stream

    @abstractmethod
    def get_manifest_event_payload(self, templates, index, presentation_time):
        return ""

    def create_emsg_boxes(self, segment_num, mod_segment, moof, representation, **kwargs):
        # start and end time of the fragment (representation timebase)
        seg_start = moof.traf.tfdt.base_media_decode_time
        seg_end = seg_start + representation.segments[mod_segment].duration

        # convert seg_start and seg_end to event timebase
        seg_start = (seg_start * self.timescale /
                     representation.timescale)
        seg_end = (seg_end * self.timescale /
                   representation.timescale)

        # print('seg start={} end={} duration={}'.format(
        #    seg_start, seg_end, seg_end - seg_start))

        # presentation_time is using event timebase
        presentation_time = self.start

        if presentation_time >= seg_end:
            return []

        if self.count > 0:
            # ev_end is using event timescale
            ev_end = presentation_time + (self.count * self.interval)
            if ev_end < seg_start:
                return []

        event_id = 0
        if seg_start > presentation_time:
            event_id = ((seg_start - presentation_time) //
                        self.interval)
        assert(event_id >= 0)
        presentation_time += event_id * self.interval
        # print('event id={0} start={1} end={2}'.format(
        #    event_id, presentation_time,
        #    presentation_time + self.duration))
        retval = []
        while presentation_time < seg_end:
            if presentation_time < seg_start:
                event_id += 1
                presentation_time += self.interval
                continue
            assert(presentation_time >= seg_start)
            data = self.get_emsg_event_payload(
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
                time_delta = presentation_time - seg_start
                kwargs['presentation_time_delta'] = time_delta
            else:
                kwargs['presentation_time'] = presentation_time
            retval.append(mp4.EventMessageBox(**kwargs))
            event_id += 1
            if self.count > 0 and event_id >= self.count:
                break
            presentation_time += self.interval
            # print('next ev id={} start={}'.format(
            #    event_id, presentation_time))
        return retval

    @abstractmethod
    def get_emsg_event_payload(self, event_id, presentation_time):
        return chr(0)

class PingPong(RepeatingEventBase):
    """
    The PingPong event scheme alternates payloads of 'ping' and 'pong'
    """
    schemeIdUri = r'urn:dash-live:pingpong:2022'

    def __init__(self, request):
        super(PingPong, self).__init__("ping_", request)

    def get_manifest_event_payload(self, templates, event_id, presentation_time):
        if (event_id & 1) == 0:
            return 'ping'
        return 'pong'

    def get_emsg_event_payload(self, event_id, presentation_time):
        data = 'ping' if (event_id & 1) == 0 else 'pong'
        return data


EventFactory.EVENT_TYPES['ping'] = PingPong

class Scte35(RepeatingEventBase):
    schemeIdUri = "urn:scte:scte35:2014:xml+bin"
    PARAMS = {
        "program_id": 1620,
    }

    def __init__(self, request):
        super(Scte35, self).__init__("scte35_", request)
        if self.inband:
            self.version = 1

    def get_manifest_event_payload(self, templates, event_id, presentation_time):
        splice = self.create_binary_signal(event_id, presentation_time)
        data = splice.encode()
        template = templates.get_template('events/scte35_xml_bin_event.xml')
        xml = template.render(binary=data)
        return xml

    def get_emsg_event_payload(self, event_id, presentation_time):
        splice = self.create_binary_signal(event_id, presentation_time)
        return splice.encode()

    def create_binary_signal(self, event_id, presentation_time):
        pts = presentation_time * MPEG_TIMEBASE / self.timescale
        duration = self.duration * MPEG_TIMEBASE / self.timescale
        # auto_return is True for the OUT and False for the IN
        auto_return = (event_id & 1) == 0
        avail_num = event_id // 2

        segmentation_descriptor = descriptors.SegmentationDescriptor(
            segmentation_event_id=avail_num,
            segmentation_duration=0,
            segmentation_type=(descriptors.SegmentationTypeId.PROVIDER_PLACEMENT_OP_START +
                               (event_id & 1)),
        )
        splice = BinarySignal(
            sap_type=SapType.CLOSED_GOP_NO_LEADING_PICTURES,
            splice_insert=SpliceInsert(
                out_of_network_indicator=True,
                splice_time={
                    "pts": pts
                },
                avails_expected=avail_num,
                splice_event_id=event_id,
                program_splice_flag=True,
                avail_num=avail_num,
                unique_program_id=self.program_id,
                break_duration={
                    "duration": duration,
                    "auto_return": auto_return,
                }
            ),
            descriptors=[
                segmentation_descriptor,
            ],
        )
        return splice


Scte35.PARAMS.update(RepeatingEventBase.PARAMS)
EventFactory.EVENT_TYPES['scte35'] = Scte35
