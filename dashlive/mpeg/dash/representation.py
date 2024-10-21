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

import datetime
from dataclasses import dataclass, field
import logging
from math import floor
import os
import sys
from typing import Any, ClassVar, NamedTuple, Optional, Set

from dashlive.drm.keymaterial import KeyMaterial
from dashlive.mpeg.codec_strings import codec_string_from_avc_box
from dashlive.mpeg.mp4 import Mp4Atom
from dashlive.utils.date_time import scale_timedelta, timecode_to_timedelta, timedelta_to_timecode
from dashlive.utils.list_of import ListOf
from dashlive.utils.object_with_fields import ObjectWithFields

from .segment import Segment
from .timing import DashTiming

class SegmentNumberAndTime(NamedTuple):
    segment_num: int  # absolute segment number
    mod_segment: int  # segment number within source media file
    origin_time: int  # time (in timescale units) to add base_media_decode_time

@dataclass(slots=True)
class SegmentTimelineElement:
    duration: int | None = None
    count: int = 0
    start: int | None = None
    mod_segment: int = 0

    def __repr__(self) -> str:
        if self.start is not None:
            return r'<S t="{}" r="{}" d="{}" />'.format(
                self.start, self.count - 1, self.duration)
        return r'<S r="{}" d="{}" />'.format(
            self.count - 1, self.duration)

    @property
    def repeat(self) -> int:
        return self.count - 1


@dataclass(slots=True)
class SegmentDurations:
    timescale: int
    segments: list[SegmentTimelineElement] = field(default_factory=list)


class SegmentPosition(NamedTuple):
    start: int
    end: int

@dataclass(slots=True)
class SegmentIndexList:
    timescale: int
    duration: int
    init: SegmentPosition
    media: list[SegmentPosition] = field(default_factory=list)


class Representation(ObjectWithFields):
    OBJECT_FIELDS = {
        'segments': ListOf(Segment),
        'kids': ListOf(KeyMaterial),
    }
    DEFAULT_VALUES = {
        'accessibility': None,
        'bitrate': None,
        'baseURL': None,
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
        'start_number': 1,
        'start_time': 0,
        'timescale': 1,
        'track_id': 1,
        'version': 0,
    }
    VERSION: ClassVar[int] = 4
    KNOWN_CODEC_BOXES: ClassVar[set[str]] = {
        'ac_3', 'avc1', 'avc3', 'mp4a', 'ec_3', 'encv', 'enca',
        'hev1', 'hvc1', 'stpp', 'wvtt',
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        defaults: dict[str, Any] = {
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
        self.num_media_segments = len(self.segments) - 1
        self._timing: DashTiming | None = None
        start: int = 0
        for seg in self.segments[1:]:
            seg.start = start
            start += seg.duration
        if self.mediaDuration is None:
            self.mediaDuration = sum([s.duration for s in self.segments[1:]])
        if self.segment_duration is None and self.num_media_segments > 0:
            self.segment_duration = int(floor(
                self.mediaDuration / self.num_media_segments))

    def __repr__(self) -> str:
        return self.as_python(exclude={'num_media_segments'})

    @classmethod
    def load(clz, filename: str, atoms: list[Mp4Atom], verbose: int = 0) -> "Representation":
        representation_start_time: int | None = None
        segment_start_time = 0
        segment_end_time = 0
        segment_start_number: int | None = None
        default_sample_duration = 0
        moov: Optional[mp4.Mp4Atom] = None
        filename = os.path.basename(filename)
        rep_id = os.path.splitext(filename)[0]
        rv = Representation(id=rep_id.lower(),
                            filename=filename,
                            version=Representation.VERSION)
        key_ids: Set[KeyMaterial] = set()
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
                if segment_start_number is None:
                    segment_start_number = atom.mfhd.sequence_number
                    rv.start_number = segment_start_number
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
                if representation_start_time is None:
                    representation_start_time = segment_start_time
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
                        rv.add_field('frameRate', float(rv.timescale) / float(default_sample_duration))
            elif atom.atom_type in ['sidx', 'moov', 'mdat', 'free'] and rv.segments:
                if verbose > 1:
                    print('Extend fragment %d with %s' % (len(rv.segments), atom.atom_type))
                seg = rv.segments[-1]
                seg.size = atom.position - seg.pos + atom.size
                if atom.atom_type == 'moov':
                    if verbose == 1:
                        sys.stdout.write('M')
                        sys.stdout.flush()
                    rv.process_moov(atom, key_ids)
                    moov = atom
        if rv.encrypted:
            rv.kids = list(key_ids)
            if rv.default_kid is None and rv.kids:
                rv.default_kid = rv.kids[0]
        if representation_start_time is None:
            rv.start_time = 0
        else:
            rv.start_time = representation_start_time
        if verbose == 1:
            sys.stdout.write('\r\n')
        if len(rv.segments) > 2:
            # We need to exclude the last fragment when trying to estimate fragment
            # duration, as the last one might be truncated. By using segment_start_time
            # of the last fragment and dividing by number of media fragments (minus one)
            # provides the best estimate of fragment duration.
            # Note: len(rv.segments) also includes the init segment, hence the need for -2
            seg_dur = segment_start_time // (len(rv.segments) - 2)
            rv.mediaDuration = 0
            for seg in rv.segments[1:]:
                rv.mediaDuration += seg.duration
            rv.max_bitrate = (8 * rv.timescale *
                              max([seg.size for seg in rv.segments]) // seg_dur)
            rv.segment_duration = seg_dur
            file_size = rv.segments[-1].pos + rv.segments[-1].size - rv.segments[0].pos
            rv.bitrate = 8 * rv.timescale * file_size // rv.mediaDuration
        return rv

    def set_dash_timing(self, timing: DashTiming) -> None:
        self._timing = timing

    def process_moov(self, moov: Mp4Atom, key_ids: set[KeyMaterial]) -> None:
        self.timescale = moov.trak.mdia.mdhd.timescale
        self.lang = moov.trak.mdia.mdhd.language
        self.track_id = moov.trak.tkhd.track_id
        try:
            default_sample_duration = moov.mvex.trex.default_sample_duration
        except AttributeError:
            print('Warning: Unable to find default_sample_duration')
            default_sample_duration = 0
        avc = None
        avc_type = None
        for box in self.KNOWN_CODEC_BOXES:
            try:
                avc = getattr(moov.trak.mdia.minf.stbl.stsd, box)
                avc_type = avc.atom_type
                break
            except AttributeError:
                pass
        if avc_type == 'enca' or avc_type == 'encv':
            avc_type = avc.sinf.frma.data_format
            self.encrypted = True
            self.default_kid = avc.sinf.schi.tenc.default_kid.encode('hex')
            self.iv_size = avc.sinf.schi.tenc.iv_size
            key_ids.add(KeyMaterial(hex=self.default_kid))
        if moov.trak.mdia.hdlr.handler_type == 'vide':
            self.process_video_moov(avc, avc_type, default_sample_duration)
        elif moov.trak.mdia.hdlr.handler_type == 'soun':
            self.process_audio_moov(avc, avc_type)
        elif moov.trak.mdia.hdlr.handler_type in {'text', 'subt'}:
            self.process_text_moov(avc, avc_type)

    def process_video_moov(self, avc: Mp4Atom, avc_type: str | None,
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
        self.codecs = codec_string_from_avc_box(avc_type, avc)
        if avc_type in {'avc1', 'avc3'}:
            self.add_field('nalLengthFieldLength',
                           avc.avcC.lengthSizeMinusOne + 1)
        elif avc_type in {'hev1', 'hvc1'}:
            self.add_field('nalLengthFieldLength',
                           avc.hvcC.length_size_minus_one + 1)

    def process_audio_moov(self, avc: Mp4Atom, avc_type: str | None) -> None:
        self.content_type = "audio"
        self.mimeType = "audio/mp4"
        self.codecs = codec_string_from_avc_box(avc_type, avc)
        if avc_type == 'mp4a':
            dsi = avc.esds.descriptor("DecoderSpecificInfo")
            self.add_field('sampleRate', dsi.sampling_frequency)
            self.add_field('numChannels', dsi.channel_configuration)
            if self.numChannels == 7:
                # 7 is a special case that means 7.1
                self.numChannels = 8
        elif avc_type == 'ec-3':
            try:
                self.add_field('sampleRate', 48000)
                self.add_field('numChannels', 0)
                for s in avc.dec3.substreams:
                    self.sampleRate = s.sampling_frequency
                    self.numChannels += s.channel_count
                    if s.lfeon:
                        self.numChannels += 1
            except AttributeError:
                self.add_field('sampleRate', avc.sampling_frequency)
                self.add_field('numChannels', 0)
        elif avc_type == 'ac-3':
            try:
                self.add_field('sampleRate', avc.dac3.sampling_frequency)
                self.add_field('numChannels', avc.dac3.channel_count)
            except AttributeError:
                self.add_field('sampleRate', avc.sampling_frequency)
                self.add_field('numChannels', avc.channel_count)

    def process_text_moov(self, avc: Mp4Atom, avc_type: str | None) -> None:
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

    def generateSegmentDurations(self) -> SegmentDurations:
        # TODO: support live profile
        def output_s_node(sn: SegmentTimelineElement) -> None:
            if sn.duration is None:
                return
            rv.segments.append(sn)
        rv = SegmentDurations(timescale=self.timescale)
        s_node = SegmentTimelineElement()
        for seg in self.segments:
            try:
                if seg.duration != s_node.duration:
                    output_s_node(s_node)
                    s_node.count = 0
                s_node.duration = seg.duration
                s_node.count += 1
            except AttributeError:
                # init segment does not have a duration
                pass
        output_s_node(s_node)
        return rv

    def generateSegmentList(self) -> SegmentIndexList:
        rv = SegmentIndexList(
            timescale=self.timescale, duration=self.mediaDuration,
            init=SegmentPosition(0, 0))
        first = True
        for seg in self.segments:
            end = seg.pos + seg.size - 1
            sp = SegmentPosition(start=seg.pos, end=end)
            if first:
                rv.init = sp
                first = False
            else:
                rv.media.append(sp)
        return rv

    def generateSegmentTimeline(self) -> list[SegmentTimelineElement]:
        def output_s_node(sn: SegmentTimelineElement) -> None:
            if sn.duration is not None:
                rv.append(sn)

        stream_ref = self._timing.stream_reference
        ref_duration_tc = stream_ref.media_duration_using_timescale(self.timescale)
        if self._timing.mode == 'live':
            timeline_start = timedelta_to_timecode(
                self._timing.firstAvailableTime, self.timescale)
            mod_segment, origin_time, seg_start_time = self.calculate_segment_from_timecode(
                timeline_start, True)
            drift = ref_duration_tc - self.mediaDuration
            end = self._timing.timeShiftBufferDepth * self.timescale
            logging.debug(
                'target=%d start=%d origin=%d mod_segment=%d drift=%d',
                timeline_start, seg_start_time, origin_time, mod_segment, drift)
        else:
            timeline_start = 0
            seg_start_time = 0
            origin_time = 0
            mod_segment = 1
            drift = 0
            end = ref_duration_tc
        rv = []
        dur = 0
        s_node = SegmentTimelineElement(mod_segment=mod_segment)
        while dur < end:
            seg = self.segments[mod_segment]
            duration = seg.duration
            if mod_segment == self.num_media_segments:
                duration += drift
            if dur == 0:
                assert seg_start_time is not None
                s_node.start = seg_start_time
            elif duration != s_node.duration:
                output_s_node(s_node)
                s_node = SegmentTimelineElement(mod_segment=mod_segment)
            s_node.duration = duration
            s_node.count += 1
            dur += duration
            mod_segment += 1
            if mod_segment > self.num_media_segments:
                mod_segment = 1
        output_s_node(s_node)
        return rv

    def timedelta_to_timescale(self, delta: datetime.timedelta) -> int:
        """
        Convert the given timedelta into the timescale used by this representation
        """
        return int(delta.total_seconds() * self.timescale)

    def timescale_to_timedelta(self, timecode: int) -> datetime.timedelta:
        """
        Convert the given timecode (in timescale units) into a timedelta
        """
        seconds = float(timecode) / float(self.timescale)
        return datetime.timedelta(seconds=seconds)

    def calculate_first_and_last_segment_number(self) -> tuple[int, int]:
        """
        Calculates the first and last available segment numbers.
        For a live stream, this will vary as time progresses based upon
        availabilityStartTime and timeShiftBufferDepth.
        """
        timing = self._timing
        if timing.mode != 'live':
            return (self.start_number, self.num_media_segments + self.start_number - 1)
        last_fragment = self.start_number + int(scale_timedelta(
            timing.elapsedTime, self.timescale, self.segment_duration))
        # For services with MPD@type='dynamic', the Segment availability start time
        # of a Media Segment is the sum of
        # - the value of the MPD@availabilityStartTime,
        # - the PeriodStart time of the containing Period as defined in subclause 5.3.2.1,
        # - the MPD start time of the Media Segment, and
        # - the MPD duration of the Media Segment
        first_fragment = (
            last_fragment - 1 -
            int(self.timescale * timing.timeShiftBufferDepth // self.segment_duration) - 1)
        first_fragment = max(self.start_number, first_fragment)
        return (first_fragment, last_fragment)

    def calculate_segment_number_and_time(
            self,
            segment_time: int | None,
            segment_num: int | None) -> SegmentNumberAndTime:
        if self._timing is None:
            raise ValueError('set_dash_timing() has not been called')

        timing = self._timing
        if timing.mode != 'live':
            if segment_num is None:
                st = segment_time + (self.segment_duration >> 2)
                segment_num = int(st // self.segment_duration) + self.start_number
            mod_segment = 1 + segment_num - self.start_number
            return SegmentNumberAndTime(segment_num, mod_segment, 0)

        # 5.3.9.5.3 Media Segment information
        # For services with MPD@type='dynamic', the Segment availability
        # start time of a Media Segment is the sum of:
        #    the value of the MPD@availabilityStartTime,
        #    the PeriodStart time of the containing Period as defined in 5.3.2.1,
        #    the MPD start time of the Media Segment, and
        #    the MPD duration of the Media Segment.
        #
        # The Segment availability end time of a Media Segment is the sum of
        # the Segment availability start time, the MPD duration of the
        # Media Segment and the value of the attribute @timeShiftBufferDepth
        # for this Representation
        if segment_time is None:
            timecode = int((segment_num - self.start_number) * self.segment_duration)
        else:
            timecode = segment_time

        if segment_num is None:
            # TODO: handle special cases where segment durations vary within
            # the reference Representation
            segment_num = int(segment_time // self.segment_duration)

        seg_delta = self.timescale_to_timedelta(timecode)
        fta = timing.firstAvailableTime - timing.leeway
        if (
                seg_delta < fta or
                seg_delta > timing.elapsedTime
        ):
            msg = (
                f'$Time$={segment_time} $Number$={segment_num} ({seg_delta}) not available ' +
                f'(valid range= {timing.firstAvailableTime} -> {timing.elapsedTime})' +
                f'(available range= {fta} -> {timing.elapsedTime})')
            raise ValueError(msg)

        mod_segment, origin_time, _ = self.calculate_segment_from_timecode(
            timecode, segment_time is None)
        logging.debug('segment=%d time=%d mod_segment=%d origin_time=%d',
                      segment_num, timecode, mod_segment, origin_time)
        return SegmentNumberAndTime(segment_num, mod_segment, origin_time)

    def calculate_segment_from_timecode(self, timecode: int,
                                        drift_compensate: bool) -> tuple[int, int, int]:
        """
        find the correct segment for the given timecode.

        :timecode: the time (in timescale units) since availabilityStartTime
            for the requested fragment.
        returns the segment number, time when the stream last looped and
        the start time of segment
        """
        rid = f'{self.content_type[0]}{self.track_id}'
        logging.debug('%s: calculate_segment_from_timecode timecode=%d (%s)',
                      rid, timecode, timecode_to_timedelta(timecode, self.timescale))

        if timecode < 0:
            raise ValueError(f"Invalid timecode: {timecode}")
        if self._timing is None:
            raise ValueError('set_dash_timing() has not been called')
        if self.num_media_segments < 2:
            raise ValueError('At least 2 media segments are required')

        mod_segment, seg_start_tc, origin_time = self.get_segment_index(timecode)
        logging.debug(
            '%s: origin=%d (%s) this_file_dur=%d (%s) mod_seg=%d',
            rid, origin_time, timecode_to_timedelta(origin_time, self.timescale),
            self.mediaDuration,
            timecode_to_timedelta(self.mediaDuration, self.timescale),
            mod_segment)
        return (mod_segment, origin_time, seg_start_tc)

    def media_duration_timedelta(self) -> datetime.timedelta:
        """
        Get the media duration, as a timedelta
        """
        if self.mediaDuration is None:
            return datetime.timedelta(0)
        return self.timescale_to_timedelta(self.mediaDuration)

    def get_segment_index(self, timecode: int) -> tuple[int, int, int]:
        assert self._timing is not None
        stream_ref = self._timing.stream_reference
        ref_duration_tc: int = stream_ref.media_duration_using_timescale(self.timescale)
        assert ref_duration_tc > 0
        num_loops: int = int(timecode // ref_duration_tc)
        origin_time: int = int(num_loops * ref_duration_tc)
        mod_segment: int = 1
        seg_start_tc: int = origin_time
        # TODO use binary search to find correct segment
        while (seg_start_tc + (self.segments[mod_segment].duration // 2)) < timecode:
            seg_start_tc += self.segments[mod_segment].duration
            mod_segment += 1
            if mod_segment > self.num_media_segments:
                mod_segment = 1
                origin_time += ref_duration_tc
                seg_start_tc = origin_time
        logging.debug(
            '%d: target=%d (%s) found=%d (%s)',
            self.track_id, timecode, timecode_to_timedelta(timecode, self.timescale),
            seg_start_tc, timecode_to_timedelta(seg_start_tc, self.timescale))
        return (mod_segment, seg_start_tc, origin_time)


if __name__ == '__main__':
    from dashlive.mpeg import mp4
    from dashlive.utils.buffered_reader import BufferedReader

    with open(sys.argv[1], 'rb') as src:
        wrap = mp4.Wrapper(children=mp4.Mp4Atom.load(BufferedReader(src)))
    rep = Representation.load(filename=sys.argv[1], atoms=wrap.children)
    print(repr(rep))
