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

from bitio import BitsFieldWriter
from objects import Binary, ObjectWithFields

class SpliceDescriptor(ObjectWithFields):
    TAGS = {}
    debug = False

    @classmethod
    def from_kwargs(cls, tag, **kwargs):
        try:
            DescriptorClass = cls.TAGS[tag]
        except KeyError:
            DescriptorClass = UnknownSpliceDescriptor
        return DescriptorClass(tag=tag, **kwargs)

    @classmethod
    def parse(cls, bit_reader):
        rv = {
            'position': bit_reader.bytepos()
        }
        r = bit_reader.duplicate(rv)
        r.read(8, 'tag')
        r.read(8, 'length')
        r.read(32, 'identifier')
        try:
            DescriptorClass = cls.TAGS[rv['tag']]
        except KeyError:
            DescriptorClass = UnknownSpliceDescriptor
        rv['_type'] = DescriptorClass.__name__
        DescriptorClass.parse(r, rv)
        return rv

    def encode(self, dest=None):
        w = BitsFieldWriter(self, dest=dest)
        w.write(8, 'tag')
        pos = w.bitpos()
        w.write(8, 'length', value=0)
        w.write(32, 'identifier')
        self.encode_fields(w)
        self.length = (w.bitpos() - pos - 8) // 8
        w.overwrite(pos, 8, 'length')
        if dest is None:
            return w.toBytes()
        return w

    @abstractmethod
    def encode_fields(self, dest):
        pass

class UnknownSpliceDescriptor(SpliceDescriptor):
    @classmethod
    def parse(cls, bit_reader, kwargs):
        bit_reader.read_bytes(kwargs['length'] - 4, 'data')

    def encode_fields(self, dest):
        dest.write_bytes(self.data)

class AvailDescriptor(SpliceDescriptor):
    TAG = 0

    @classmethod
    def parse(cls, bit_reader, kwargs):
        bit_reader.read(32, 'provider_avail_id')

    def encode_fields(self, dest):
        dest.write(32, 'provider_avail_id')


class DtmfDescriptor(SpliceDescriptor):
    TAG = 1

    @classmethod
    def parse(cls, bit_reader, kwargs):
        bit_reader.read(8, 'preroll')
        bit_reader.read(3, 'dtmf_count')
        bit_reader.get(5, 'reserved')
        chars = []
        for idx in range(kwargs['dtmf_count']):
            chars.append(chr(bit_reader.get(8, 'dtmf_char')))
        kwargs['chars'] = ''.join(chars)

    def encode_fields(self, dest):
        w = BitsFieldWriter(self, dest=dest)
        self.dtmf_count = len(self.chars)
        w.write(8, 'preroll')
        w.write(3, 'dtmf_count')
        w.write(5, 'reserved', value=0x1F)
        w.write_bytes(self.chars)


class SegmentationTypeId(object):
    NOT_INDICATED = 0x00
    CONTENT_ID = 0x01
    PROGRAM_START = 0x10
    PROGRAM_END = 0x11
    PROGRAM_EARLY_TERMINATION = 0x12
    PROGRAM_BREAKAWAY = 0x13
    PROGRAM_RETURN = 0x14
    PROGRAM_OVERRUN_PLANNED = 0x15
    PROGRAM_OVERRUN_UNPLANNED = 0x16
    PROGRAM_OVERLAP_START = 0x17
    PROGRAM_BLACKOUT_OVERRIDE = 0x18
    PROGRAM_JOIN = 0x19
    CHAPTER_START = 0x20
    CHAPTER_END = 0x21
    BREAK_START = 0x22
    BREAK_END = 0x23
    OPENING_CREDIT_START = 0x24
    OPENING_CREDIT_END = 0x25
    CLOSING_CREDIT_START = 0x26
    CLOSING_CREDIT_END = 0x27
    PROVIDER_AD_START = 0x30
    PROVIDER_AD_END = 0x31
    DISTRIBUTOR_AD_START = 0x32
    DISTRIBUTOR_AD_END = 0x33
    PROVIDER_PLACEMENT_OP_START = 0x34
    PROVIDER_PLACEMENT_OP_END = 0x35
    DISTRIBUTOR_PLACEMENT_OP_START = 0x36
    DISTRIBUTOR_PLACEMENT_OP_END = 0x37
    PROVIDER_OVERLAY_PLACEMENT_OP_START = 0x38
    PROVIDER_OVERLAY_PLACEMENT_OP_END = 0x39
    DISTRIBUTOR_OVERLAY_PLACEMENT_OP_START = 0x3A
    DISTRIBUTOR_OVERLAY_PLACEMENT_OP_END = 0x3B
    PROVIDER_PROMO_START = 0x3E
    PROVIDER_PROMO_END = 0x3F
    UNSCHEDULED_EVENT_START = 0x40
    UNSCHEDULED_EVENT_END = 0x41
    PROVIDER_AD_BLOCK_START = 0x44
    PROVIDER_AD_BLOCK_END = 0x45
    DISTRIBUTOR_AD_BLOCK_START = 0x44
    DISTRIBUTOR_AD_BLOCK_END = 0x45


class SegmentationDescriptor(SpliceDescriptor):
    TAG = 2
    IDENTIFIER = 0x43554549  # "CUEI"
    DEFAULT_VALUES = {
        'delivery_not_restricted_flag': True,
        'identifier': IDENTIFIER,
        'segmentation_event_cancel_indicator': False,
        'program_segmentation_flag': True,
        'segmentation_upid_type': 0x0F,  # no UPID
        'segmentation_upid': None,
        'segment_num': 0,
        'segments_expected': 0,
        'sub_segment_num': 0,
        'sub_segments_expected': 0,
    }
    OBJECT_FIELDS = {
        'segmentation_upid': Binary,
    }

    @classmethod
    def parse(cls, r, kwargs):
        r.read(32, 'segmentation_event_id')
        r.read(1, 'segmentation_event_cancel_indicator')
        r.get(7, 'reserved')
        if kwargs['segmentation_event_cancel_indicator']:
            return
        r.read(1, 'program_segmentation_flag')
        r.read(1, 'segmentation_duration_flag')
        r.read(1, 'delivery_not_restricted_flag')
        if kwargs['delivery_not_restricted_flag']:
            r.get(5, 'reserved')
            kwargs['web_delivery_allowed_flag'] = True
            kwargs['no_regional_blackout_flag'] = True
            kwargs['archive_allowed_flag'] = True
            kwargs['device_restrictions'] = 0x03  # no restrictions
        else:
            r.read(1, 'web_delivery_allowed_flag')
            r.read(1, 'no_regional_blackout_flag')
            r.read(1, 'archive_allowed_flag')
            r.read(2, 'device_restrictions')
        if not kwargs['program_segmentation_flag']:
            count = r.get(8, 'component_count')
            kwargs['components'] = []
            for idx in range(count):
                tag = r.get(8, 'tag')
                r.get(7, 'reserved')
                pts_offset = r.get(33, 'pts_offset')
                kwargs['components'].push({
                    'component_tag': tag,
                    'pts_offset': pts_offset
                })
        else:
            kwargs['components'] = None
        if kwargs['segmentation_duration_flag']:
            r.read(40, 'segmentation_duration')
        else:
            kwargs['segmentation_duration'] = None
        r.read(8, 'segmentation_upid_type')
        upid_length = r.get(8, 'segmentation_upid_length')
        r.read_bytes(upid_length, 'segmentation_upid')
        r.read(8, 'segmentation_type_id')
        r.read(8, 'segment_num')
        r.read(8, 'segments_expected')
        if kwargs['segmentation_type_id'] in {0x34, 0x36, 0x38, 0x3A}:
            r.read(8, 'sub_segment_num')
            r.read(8, 'sub_segments_expected')

    def encode_fields(self, dest):
        if self.segmentation_upid is None:
            self.segmentation_upid_type = 0x0F
        self.segmentation_duration_flag = self.segmentation_duration is not None
        w = BitsFieldWriter(self, dest=dest)
        w.write(32, 'segmentation_event_id')
        w.write(1, 'segmentation_event_cancel_indicator')
        w.write(7, 'reserved', value=0x7F)
        if self.segmentation_event_cancel_indicator:
            return
        w.write(1, 'program_segmentation_flag')
        w.write(1, 'segmentation_duration_flag')
        w.write(1, 'delivery_not_restricted_flag')
        if self.delivery_not_restricted_flag:
            w.write(5, 'reserved', value=0x1F)
        else:
            w.write(1, 'web_delivery_allowed_flag')
            w.write(1, 'no_regional_blackout_flag')
            w.write(1, 'archive_allowed_flag')
            w.write(2, 'device_restrictions')
        if not self.program_segmentation_flag:
            self.component_count = len(self.components)
            for comp in self.components:
                w.write(8, 'tag', value=comp['component_tag'])
                w.write(7, 'reserved', value=0x7F)
                w.write(33, 'pts_offset', value=comp['pts_offset'])
        if self.segmentation_duration_flag:
            w.write(40, 'segmentation_duration')
        w.write(8, 'segmentation_upid_type')
        if self.segmentation_upid is None:
            w.write(8, 'segmentation_upid_length', value=0)
        else:
            upid_length = len(self.segmentation_upid)
            w.write(8, 'segmentation_upid_length', value=upid_length)
            w.write_bytes('segmentation_upid', value=self.segmentation_upid.data)
        w.write(8, 'segmentation_type_id')
        w.write(8, 'segment_num')
        w.write(8, 'segments_expected')
        if self.segmentation_type_id in {0x34, 0x36, 0x38, 0x3A}:
            w.write(8, 'sub_segment_num')
            w.write(8, 'sub_segments_expected')


class TimeDescriptor(SpliceDescriptor):
    TAG = 3

    @classmethod
    def parse(cls, r, kwargs):
        r.read(48, 'TAI_seconds')
        r.read(32, 'TAI_ns')
        r.read(16, 'UTC_offset')

    def encode_fields(self, dest):
        w = BitsFieldWriter(self, dest=dest)
        w.write(48, 'TAI_seconds')
        w.write(32, 'TAI_ns')
        w.write(16, 'UTC_offset')


class AudioDescriptor(SpliceDescriptor):
    TAG = 4

    @classmethod
    def parse(cls, r, kwargs):
        count = r.get(4, 'audio_count')
        r.get(4, 'reserved')
        components = []
        for idx in range(count):
            components.append({
                'tag': r.get(8, 'component_tag'),
                'ISO_code': r.get(24, 'ISO_code'),
                'Bit_Stream_Mode': r.get(3, 'Bit_Stream_Mode'),
                'Num_Channels': r.get(4, 'Num_Channels'),
                'Full_Srvc_Audio': r.get(1, 'Full_Srvc_Audio'),
            })
        kwargs['audio_components'] = components

    def encode_fields(self, dest):
        w = BitsFieldWriter(self, dest=dest)
        w.write(4, 'audio_count', value=len(self.audio_components))
        w.write(4, 'reserved', 0x0F)
        for comp in self.audio_components:
            cw = w.duplicate(comp)
            cw.write(8, 'tag')
            cw.write(24, 'ISO_code')
            cw.write(3, 'Bit_Stream_Mode')
            cw.write(4, 'Num_Channels')
            cw.write(1, 'Full_Srvc_Audio')


for desc in [AvailDescriptor, DtmfDescriptor, SegmentationDescriptor,
             TimeDescriptor, AudioDescriptor]:
    desc.DEFAULT_VALUES['tag'] = desc.TAG
    SpliceDescriptor.TAGS[desc.TAG] = desc
