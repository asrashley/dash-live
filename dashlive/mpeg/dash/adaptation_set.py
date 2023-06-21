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

from __future__ import division
from past.utils import old_div
from builtins import object

from dashlive.mpeg.dash.event_stream import EventStream
from dashlive.utils.objects import dict_to_cgi_params
from dashlive.utils.list_of import ListOf
from dashlive.utils.object_with_fields import ObjectWithFields

from .representation import Representation

class ContentComponent(object):
    def __init__(self, id, content_type):
        self.id = id
        self.contentType = content_type

class AdaptationSet(ObjectWithFields):
    OBJECT_FIELDS = {
        'event_streams': ListOf(EventStream),
        'representations': ListOf(Representation),
    }
    DEFAULT_VALUES = {
        'maxSegmentDuration': 1,
        'startNumber': 1,
        'timescale': 1,
        'segmentAlignment': True,
    }

    def __init__(self, **kwargs):
        """
        Required kwargs:
        mode
        content_type
        """
        super(AdaptationSet, self).__init__(**kwargs)
        defaults = {
            'id': hash(self),
            'representations': [],
            'event_streams': [],
        }
        if self.content_type == 'audio':
            defaults['mimeType'] = "audio/mp4"
            defaults['lang'] = 'und'
            defaults['role'] = 'main'
            suffix = 'm4a'
        elif self.content_type == 'video':
            defaults['mimeType'] = "video/mp4"
            defaults['startWithSAP'] = 1
            defaults['par'] = "16:9"
            suffix = 'm4v'
        elif self.content_type == 'text':
            defaults['lang'] = 'und'
            defaults['role'] = 'subtitle'
            if kwargs.get('codecs', None) == 'wvtt':
                defaults['mimeType'] = 'text/vtt'
            else:
                defaults['mimeType'] = 'application/mp4'
            suffix = 'mp4'
        else:
            defaults['mimeType'] = 'application/mp4'
            suffix = 'mp4'
        if self.mode == 'odvod':
            defaults['mediaURL'] = r'$RepresentationID$.' + suffix
        else:
            defaults['initURL'] = r'$RepresentationID$/init.' + suffix
            defaults['mediaURL'] = r'$RepresentationID$/$Number$.' + suffix
        defaults['fileSuffix'] = suffix
        self.apply_defaults(defaults)

    @property
    def contentComponent(self):
        return ContentComponent(self.id, self.content_type)

    def key_ids(self):
        kids = set()
        for rep in self.representations:
            if rep.encrypted:
                kids.update(rep.kids)
        return kids

    def append_cgi_params(self, params):
        if not params:
            return
        qs = dict_to_cgi_params(params)
        self.mediaURL += qs
        if self.mode != 'odvod':
            self.initURL += qs

    def compute_av_values(self):
        if not self.representations:
            return
        self.timescale = self.representations[0].timescale
        self.presentationTimeOffset = int(
            (self.startNumber - 1) * self.representations[0].segment_duration)
        self.minBitrate = min([a.bitrate for a in self.representations])
        self.maxBitrate = max([a.bitrate for a in self.representations])
        self.maxSegmentDuration = old_div(max(
            [a.segment_duration for a in self.representations]), self.timescale)

        if self.content_type in {'audio', 'text'}:
            for rep in self.representations:
                if rep.lang:
                    self.lang = rep.lang
                if self.content_type == 'audio':
                    self.sampleRate = rep.sampleRate
                    self.numChannels = rep.numChannels
        elif self.content_type == 'video':
            self.minWidth = min(
                [a.width for a in self.representations])
            self.minHeight = min(
                [a.height for a in self.representations])
            self.maxWidth = max(
                [a.width for a in self.representations])
            self.maxHeight = max(
                [a.height for a in self.representations])
            self.maxFrameRate = max(
                [a.frameRate for a in self.representations])

    def set_reference_representation(self, ref_representation):
        for rep in self.representations:
            rep.set_reference_representation(ref_representation)

    def set_dash_timing(self, timing):
        for rep in self.representations:
            rep.set_dash_timing(timing)
