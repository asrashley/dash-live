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

from __future__ import print_function
from __future__ import division
from builtins import str
from past.utils import old_div
from builtins import object
import datetime
import os
import sys
from typing import List, Optional

import bitstring

from dashlive.drm.keymaterial import KeyMaterial
from dashlive.mpeg.mp4 import Mp4Atom
from dashlive.utils.date_time import scale_timedelta
from dashlive.utils.list_of import ListOf
from dashlive.utils.object_with_fields import ObjectWithFields

from .segment import Segment

class SegmentTimelineElement(object):
    def __init__(self, duration=None, count=0, start=None):
        self.duration = duration
        self.count = count
        self.start = start

    def __repr__(self):
        if self.start is not None:
            return r'<S t="{0}" r="{1}" d="{2}" />'.format(
                self.start, self.count - 1, self.duration)
        return r'<S r="{0}" d="{1}" />'.format(
            self.count - 1, self.duration)

    @property
    def repeat(self):
        return self.count - 1


class Representation(ObjectWithFields):
    OBJECT_FIELDS = {
        'segments': ListOf(Segment),
        'kids': ListOf(KeyMaterial),
    }
    DEFAULT_VALUES = {
        'accessibility': None,
        'bitrate': None,
        'content_type': None,
        'codecs': None,
        'default_kid': None,
        'iv_size': None,
        'encrypted': False,
        'mediaDuration': None,
        'max_bitrate': None,
        'mimeType': None,
        'nalLengthFieldLength': None,
        'segment_duration': None,
        'startWithSAP': 1,
        'timescale': 1,
        'track_id': 1,
        'version': 0,
    }
    VERSION = 3
    KNOWN_CODEC_BOXES = [
        'ac_3', 'avc1', 'avc3', 'mp4a', 'ec_3', 'encv', 'enca',
        'hev1', 'hvc1', 'stpp', 'wvtt',
    ]

    def __init__(self, **kwargs):
        super(Representation, self).__init__(**kwargs)
        defaults = {
            'lang': kwargs.get('language', 'und'),
            'kids': [],
            'segments': [],
            'codecs': '',
        }
        if self.content_type == 'video':
            defaults.update({
                'frameRate': None,
                'height': None,
                'scanType': "progressive",
                'sar': "1:1",
                'width': None,
            })
        elif self.content_type == 'audio':
            defaults.update({
                'sampleRate': 48000,
                'numChannels': 1,
            })
        self.apply_defaults(defaults)
        self.num_segments = len(self.segments) - 1
        self._ref_representation: Optional[Representation] = None

    def __repr__(self):
        return self.as_python(exclude={'num_segments'})

    @classmethod
    def load(clz, filename: str, atoms: List[Mp4Atom], verbose: int = 0) -> "Representation":
        segment_start_time = 0
        segment_end_time = 0
        default_sample_duration = 0
        moov = None
        filename = os.path.basename(filename)
        rep_id = os.path.splitext(filename)[0]
        rv = Representation(id=rep_id.lower(),
                            filename=filename,
                            version=Representation.VERSION)
        key_ids = set()
        for atom in atoms:
            seg = Segment(pos=atom.position, size=atom.size)
            if verbose > 2:
                print('atom', str(atom.atom_type, 'ascii'))
            if atom.atom_type == 'ftyp':
                if verbose > 1:
                    print(('Init seg', atom))
                elif verbose > 0:
                    sys.stdout.write('I')
                    sys.stdout.flush()
                rv.segments.append(seg)
            elif atom.atom_type == 'moof':
                if verbose > 1:
                    print('Fragment %d ' % (len(rv.segments) + 1))
                elif verbose > 0:
                    sys.stdout.write('f')
                    sys.stdout.flush()
                dur = 0
                for sample in atom.traf.trun.samples:
                    if not sample.duration:
                        sample.duration = moov.mvex.trex.default_sample_duration
                    dur += sample.duration
                seg.duration = dur
                try:
                    for kid in atom.pssh.key_ids:
                        key_ids.add(KeyMaterial(raw=kid))
                except AttributeError:
                    pass
                tfdt = atom.traf.find_child('tfdt')
                if tfdt is None:
                    segment_start_time = segment_end_time
                else:
                    segment_start_time = atom.traf.tfdt.base_media_decode_time
                    segment_end_time = segment_start_time
                for sample in atom.traf.trun.samples:
                    segment_end_time += sample.duration
                rv.segments.append(seg)
                if default_sample_duration == 0:
                    for sample in atom.traf.trun.samples:
                        default_sample_duration += sample.duration
                    default_sample_duration = default_sample_duration // len(atom.traf.trun.samples)
                    if verbose > 1:
                        print('Average sample duration %d' % default_sample_duration)
                    if rv.content_type == "video" and default_sample_duration:
                        rv.add_field('frameRate', old_div(rv.timescale, default_sample_duration))
            elif atom.atom_type in ['sidx', 'moov', 'mdat', 'free'] and rv.segments:
                if verbose > 1:
                    print('Extend fragment %d with %s' % (len(rv.segments), atom.atom_type))
                seg = rv.segments[-1]
                seg.size = atom.position - seg.pos + atom.size
                if atom.atom_type == 'moov':
                    if verbose == 1:
                        sys.stdout.write('M')
                        sys.stdout.flush()
                    clz.process_moov(atom, rv, key_ids)
                    moov = atom
        if rv.encrypted:
            rv.kids = list(key_ids)
        if verbose == 1:
            sys.stdout.write('\r\n')
        if len(rv.segments) > 2:
            # We need to exclude the last fragment when trying to estimate fragment
            # duration, as the last one might be truncated. By using segment_start_time
            # of the last fragment and dividing by number of media fragments (minus one)
            # provides the best estimate of fragment duration.
            # Note: len(rv.segments) also includes the init segment, hence the need for -2
            seg_dur = old_div(segment_start_time, (len(rv.segments) - 2))
            rv.mediaDuration = 0
            for seg in rv.segments[1:]:
                rv.mediaDuration += seg.duration
            rv.max_bitrate = old_div(8 * rv.timescale * max([seg.size for seg in rv.segments]), seg_dur)
            rv.segment_duration = seg_dur
            file_size = rv.segments[-1].pos + rv.segments[-1].size - rv.segments[0].pos
            rv.bitrate = int(old_div(8 * rv.timescale * file_size, rv.mediaDuration) + 0.5)
        return rv

    def set_reference_representation(self, ref_representation: "Representation") -> None:
        if ref_representation == self:
            self._ref_representation = None
        else:
            self._ref_representation = ref_representation

    def set_dash_timing(self, timing):
        self.timing = timing

    @classmethod
    def process_moov(clz, moov: Mp4Atom, rv: Mp4Atom, key_ids: Mp4Atom) -> None:
        rv.timescale = moov.trak.mdia.mdhd.timescale
        rv.lang = moov.trak.mdia.mdhd.language
        rv.track_id = moov.trak.tkhd.track_id
        try:
            default_sample_duration = moov.mvex.trex.default_sample_duration
        except AttributeError:
            print('Warning: Unable to find default_sample_duration')
            default_sample_duration = 0
        avc = None
        avc_type = None
        for box in clz.KNOWN_CODEC_BOXES:
            try:
                avc = getattr(moov.trak.mdia.minf.stbl.stsd, box)
                avc_type = avc.atom_type
                break
            except AttributeError:
                pass
        if avc_type == 'enca' or avc_type == 'encv':
            avc_type = avc.sinf.frma.data_format
            rv.encrypted = True
            rv.default_kid = avc.sinf.schi.tenc.default_kid.encode('hex')
            rv.iv_size = avc.sinf.schi.tenc.iv_size
            key_ids.add(KeyMaterial(hex=rv.default_kid))
        if moov.trak.mdia.hdlr.handler_type == 'vide':
            rv.process_video_moov(avc, avc_type, default_sample_duration)
        elif moov.trak.mdia.hdlr.handler_type == 'soun':
            rv.process_audio_moov(avc, avc_type)
        elif moov.trak.mdia.hdlr.handler_type in {'text', 'subt'}:
            rv.process_text_moov(avc, avc_type)

    def process_video_moov(self, avc: Mp4Atom, avc_type: Optional[str],
                           default_sample_duration: int) -> None:
        trak = avc.find_atom('trak')
        self.content_type = "video"
        self.mimeType = "video/mp4"
        if default_sample_duration > 0:
            self.add_field('frameRate',
                           self.timescale // default_sample_duration)
        self.add_field('width', int(trak.tkhd.width))
        self.add_field('height', int(trak.tkhd.height))
        try:
            self.width = avc.width
            self.height = avc.height
        except AttributeError:
            pass
        # TODO: work out scan type
        self.add_field('scanType', "progressive")
        # TODO: work out sample aspect ratio
        self.add_field('sar', "1:1")
        if avc_type in {'avc1', 'avc3'}:
            self.codecs = '%s.%02x%02x%02x' % (
                avc_type,
                avc.avcC.AVCProfileIndication,
                avc.avcC.profile_compatibility,
                avc.avcC.AVCLevelIndication)
            self.add_field('nalLengthFieldLength',
                           avc.avcC.lengthSizeMinusOne + 1)
        elif avc_type in {'hev1', 'hvc1'}:
            # According to ISO 14496-15, the codec string for hev1 and hvc1
            # should be:
            # * the general_profile_space, encoded as no character
            #   (general_profile_space == 0), or 'A', 'B', 'C' for
            #   general_profile_space 1, 2, 3, followed by the general_profile_idc
            #   encoded as a decimal number;
            # * the general_profile_compatibility_flags, encoded in hexadecimal
            #   (leading zeroes may be omitted);
            # * the general_tier_flag, encoded as 'L' (general_tier_flag==0) or
            #   'H' (general_tier_flag==1), followed by the general_level_idc,
            #   encoded as a decimal number;
            # * each of the 6 bytes of the constraint flags, starting from the byte
            #   containing the general_progressive_source_flag, each encoded as a
            #   hexadecimal number, and the encoding of each byte separated by a
            #   period; trailing bytes that are zero may be omitted.
            gps = ['', 'A', 'B', 'C'][avc.hvcC.general_profile_space]
            tier = '{0}{1}'.format(
                'LH'[avc.hvcC.general_tier_flag],
                avc.hvcC.general_level_idc)
            gpcf = bitstring.BitArray(
                uint=avc.hvcC.general_profile_compatibility_flags, length=32)
            gpcf.reverse()
            parts = [
                str(avc_type),
                '{0}{1:d}'.format(gps, avc.hvcC.general_profile_idc),
                '{0:x}'.format(gpcf.uint),
                tier,
            ]
            gcif = avc.hvcC.general_constraint_indicator_flags
            pos = 40
            while gcif > 0:
                mask = 0xFF << pos
                parts.append(r'{:x}'.format((gcif & mask) >> pos))
                gcif = gcif & ~mask
                pos -= 8
            self.codecs = '.'.join(parts)
            self.add_field('nalLengthFieldLength',
                           avc.hvcC.length_size_minus_one + 1)

    def process_audio_moov(self, avc: Mp4Atom, avc_type: Optional[str]) -> None:
        self.content_type = "audio"
        self.mimeType = "audio/mp4"
        self.codecs = avc_type
        if avc_type == 'mp4a':
            dsi = avc.esds.descriptor("DecoderSpecificInfo")
            self.add_field('sampleRate', dsi.sampling_frequency)
            self.add_field('numChannels', dsi.channel_configuration)
            self.codecs = "%s.%02x.%x" % (
                avc_type, dsi.object_type,
                dsi.audio_object_type)
            if self.numChannels == 7:
                # 7 is a special case that means 7.1
                self.numChannels = 8
        elif avc_type == 'ec-3':
            try:
                self.add_field('sampleRate', avc.sampling_frequency)
                self.add_field('numChannels', 0)
                for s in avc.dec3.substreams:
                    self.numChannels += s.channel_count
                    if s.lfeon:
                        self.numChannels += 1
            except AttributeError:
                pass
        elif avc_type == 'ac-3':
            try:
                self.add_field('sampleRate', avc.dac3.sampling_frequency)
                self.add_field('numChannels', avc.dac3.channel_count)
            except AttributeError:
                self.add_field('sampleRate', avc.sampling_frequency)
                self.add_field('numChannels', avc.channel_count)

    def process_text_moov(self, avc: Mp4Atom, avc_type: Optional[str]) -> None:
        self.content_type = 'text'
        self.codecs = avc_type
        self.mimeType = 'application/mp4'
        if avc_type == 'wvtt':
            self.mimeType = 'text/vtt'
        elif avc_type == 'stpp':
            trak = avc.find_atom('trak')
            stpp = trak.mdia.minf.stbl.stsd.stpp
            if stpp.mime_types:
                self.mimeType = stpp.mime_types
            try:
                parts = stpp.mime.content_type.split(';')
                self.mimeType = parts[0]
                if len(parts) > 1 and parts[1].startswith('codecs='):
                    self.codecs = parts[1][len('codecs='):]
            except AttributeError:
                pass

    def generateSegmentDurations(self):
        # TODO: support live profile
        def output_s_node(sn):
            if sn["duration"] is None:
                return
            rv['segments'].append(sn)
        rv = dict(timescale=self.timescale, segments=[])
        s_node = {
            "duration": None,
            "count": 0,
        }
        for seg in self.segments:
            try:
                if seg.duration != s_node["duration"]:
                    output_s_node(s_node)
                    s_node["count"] = 0
                s_node["duration"] = seg.duration
                s_node["count"] += 1
            except AttributeError:
                # init segment does not have a duration
                pass
        output_s_node(s_node)
        return rv

    def generateSegmentList(self):
        # TODO: support live profile
        rv = {
            'timescale': self.timescale,
            'duration': self.mediaDuration,
            'media': [],
        }
        first = True
        for seg in self.segments:
            if first:
                rv['init'] = {
                    'start': seg.pos,
                    'end': seg.pos + seg.size - 1,
                }
                first = False
            else:
                rv['media'].append({
                    'start': seg.pos,
                    'end': seg.pos + seg.size - 1,
                })
        return rv

    def generateSegmentTimeline(self):
        def output_s_node(sn):
            if sn.duration is None:
                return
            rv.append(sn)
        rv = []
        if self.timing.mode == 'live':
            timeline_start = (
                self.timing.elapsedTime -
                datetime.timedelta(seconds=self.timing.timeShiftBufferDepth))
        else:
            timeline_start = datetime.timedelta(seconds=0)
        first = True
        segment_num, origin_time = self.calculate_segment_from_timecode(
            scale_timedelta(timeline_start, 1, 1))
        assert segment_num < len(self.segments)
        # seg_start_time is the time (in representation timescale units) when the segment_num
        # segment started, relative to availabilityStartTime
        seg_start_time = int(origin_time * self.timescale +
                             (segment_num - 1) * self.segment_duration)
        dur = 0
        s_node = SegmentTimelineElement()
        if self.timing.mode == 'live':
            end = self.timing.timeShiftBufferDepth * self.timescale
        else:
            end = self.timing.mediaDuration.total_seconds() * self.timescale
        while dur <= end:
            seg = self.segments[segment_num]
            if first:
                assert seg_start_time is not None
                s_node.start = seg_start_time
                first = False
            elif seg.duration != s_node.duration:
                output_s_node(s_node)
                s_node = SegmentTimelineElement()
            s_node.duration = seg.duration
            s_node.count += 1
            dur += seg.duration
            segment_num += 1
            if segment_num > self.num_segments:
                segment_num = 1
        output_s_node(s_node)
        return rv

    def calculate_segment_from_timecode(self, timecode):
        """
        find the correct segment for the given timecode.

        :timecode: the time (in seconds) since availabilityStartTime
            for the requested fragment.
        returns the segment number and the time when the stream last looped
        """
        if timecode < 0:
            raise ValueError("Invalid timecode: %d" % timecode)
        # nominal_duration is the duration (in timescale units) of the reference
        # representation. This is used to decide how many times the stream has looped
        # since availabilityStartTime.
        if self._ref_representation is None:
            ref_representation = self
        else:
            ref_representation = self._ref_representation
        nominal_duration = ref_representation.segment_duration * \
            ref_representation.num_segments
        tc_scaled = int(timecode * ref_representation.timescale)
        num_loops = old_div(tc_scaled, nominal_duration)

        # origin time is the time (in timescale units) that maps to segment 1 for
        # all adaptation sets. It represents the most recent time of day when the
        # content started from the beginning, relative to availabilityStartTime
        origin_time = num_loops * nominal_duration

        # print('origin_time', timecode, origin_time, num_loops,
        #      float(nominal_duration) / float(ref_representation.timescale))
        # print('segment_duration', ref_representation.segment_duration,
        #      float(ref_representation.segment_duration) /
        #      float(ref_representation.timescale))

        # the difference between timecode and origin_time now needs
        # to be mapped to the segment index of this representation
        segment_num = (tc_scaled - origin_time) * self.timescale
        segment_num /= ref_representation.timescale
        segment_num /= self.segment_duration
        segment_num = int(segment_num + 1)
        # the difference between the segment durations of the reference
        # representation and this representation can mean that this representation
        # has already looped
        if segment_num > self.num_segments:
            segment_num = 1
            origin_time += nominal_duration
        origin_time /= ref_representation.timescale
        if segment_num < 1 or segment_num > self.num_segments:
            raise ValueError(f'Invalid segment number {segment_num}')
        return (segment_num, origin_time)


if __name__ == '__main__':
    from dashlive.mpeg import mp4
    from dashlive.utils.buffered_reader import BufferedReader

    with open(sys.argv[1], 'rb') as src:
        wrap = mp4.Wrapper(children=mp4.Mp4Atom.load(BufferedReader(src)))
    rep = Representation.load(filename=sys.argv[1], atoms=wrap.children)
    print(repr(rep))
