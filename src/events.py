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

import mp4
import utils

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
                ev = cls.EVENT_TYPES[name]
                retval.append(ev(request))
            except KeyError as err:
                print(err)
                continue
        if not retval:
            return []
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
                value = utils.from_isodatetime(value)
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

    def __init__(self, prefix, request):
        super(RepeatingEventBase, self).__init__(prefix, request)

    def create_manifest_context(self, context, templates):
        stream = {
            'schemeIdUri': self.schemeIdUri,
            'value': self.value,
            'timescale': self.timescale,
            'inband': self.inband,
        }
        if not self.inband and self.count > 0:
            stream['events'] = []
            presentation_time = self.start
            for idx in range(self.count):
                data = self.get_manifest_event_payload(templates, idx, presentation_time)
                stream['events'].append({
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


EventFactory.EVENT_TYPES['ping'] = PingPong
