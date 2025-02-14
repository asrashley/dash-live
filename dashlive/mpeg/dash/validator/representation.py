#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import asyncio
from collections.abc import Awaitable
import datetime
import math
import re
from typing import Any, ClassVar, Optional, Set, TYPE_CHECKING, cast
import urllib.parse

from lxml import etree as ET

from dashlive.mpeg.dash.representation import Representation as DashRepresentation
from dashlive.utils.date_time import (
    multiply_timedelta,
    scale_timedelta,
    timecode_to_timedelta,
    timedelta_to_timecode,
)

from .dash_element import DashElement
from .init_segment import InitSegment
from .media_segment import MediaSegment
from .multiple_segment_base_type import MultipleSegmentBaseType
from .representation_base_type import RepresentationBaseType
from .validation_flag import ValidationFlag

if TYPE_CHECKING:
    from .adaptation_set import AdaptationSet
    from .period import Period

class Representation(RepresentationBaseType):
    attributes: ClassVar[list[tuple[str, Any, Any]]] = RepresentationBaseType.attributes + [
        ('bandwidth', int, None),
        ('id', str, None),
        ('qualityRanking', int, None),
        ('dependencyId', str, None),
    ]

    timeline_start: int  # from start of stream (manifest timescale units)
    parent: "AdaptationSet"

    def __init__(self, elt: ET.ElementBase, parent: DashElement) -> None:
        super().__init__(elt, parent)
        self.media_segments: list[MediaSegment] = []
        self.segmentBase: Optional[MultipleSegmentBaseType] = None
        self._validated = False
        if self.mimeType is None:
            self.mimeType = self.parent.mimeType
        if self.id:
            self.attrs.prefix = f'{self.id}: '
            self.elt.prefix = f'{self.id}: '
        if self.segmentTemplate is None:
            self.segmentTemplate = parent.segmentTemplate
        if self.mode == "odvod":
            segmentBase = elt.findall('./dash:SegmentBase', self.xmlNamespaces)
            self.elt.check_less_than(len(segmentBase), 2)
            if len(segmentBase):
                self.segmentBase = MultipleSegmentBaseType(
                    segmentBase[0], self)
        if self.mode == 'odvod':
            self.init_segment = self.create_init_segment_on_demand_profile()
        else:
            self.init_segment = self.create_init_segment_live_profile()

    @property
    def period(self) -> "Period":
        return cast("Period", self.parent.parent)

    @property
    def target_duration(self) -> datetime.timedelta | None:
        return self.period.target_duration

    async def merge_previous_element(self, prev: "Representation") -> bool:
        if self.mode != 'live':
            self.log.error('merge_previous_element called for a non-live stream')
            return False
        self.log.debug('Merging previous representation %s', prev.id)
        if prev.init_segment is not None:
            self.init_segment = prev.init_segment
            self.log.debug(
                '%s: Reusing previous init segment. has_atoms=%s',
                self.id, self.init_segment.atoms is not None)
        self.media_segments = []
        if not await self.generate_segments_live_profile():
            return False
        seg_names: Set[str] = set()
        merged_segments = []
        for seg in prev.media_segments:
            merged_segments.append(seg)
            self.log.debug(
                '%s: preserve media segment %s', self.id, seg.name)
            seg_names.add(seg.name)
        for seg in self.media_segments:
            if seg.name not in seg_names:
                self.log.debug('%s: add media segment %s', self.id, seg.name)
                merged_segments.append(seg)
        self.log.debug('%s: Merged %d media segments', self.id,
                       len(merged_segments))
        self.media_segments = merged_segments
        return True

    async def prefetch_media_info(self) -> bool:
        rv = await self.init_segment.load()

        if rv and len(self.media_segments) == 0:
            if self.mode == "odvod":
                rv = await self.generate_segments_on_demand_profile()
            else:
                rv = await self.generate_segments_live_profile()
        self.progress.inc()
        return rv

    def set_representation_info(self, info: DashRepresentation):
        self.init_segment.set_dash_representation(info)

    def init_seg_url(self) -> str | None:
        if self.mode == 'odvod':
            return self.format_url_template(self.baseurl)
        if self.segmentTemplate is None:
            return None
        if self.segmentTemplate.initialization is None:
            return None
        url = self.format_url_template(self.segmentTemplate.initialization)
        if self.baseurl is None:
            return url
        return urllib.parse.urljoin(self.baseurl, url)

    async def generate_segments_live_profile(self) -> bool:
        if not self.elt.check_not_equal(self.mode, 'odvod'):
            return False
        if not self.elt.check_not_none(
                self.segmentTemplate,
                msg='SegmentTemplate is required when using live profile'):
            return False
        if not await self.init_segment.load():
            return False
        frameRate = 24
        if self.frameRate is not None:
            frameRate = self.frameRate.value
        elif self.parent.maxFrameRate is not None:
            frameRate = self.parent.maxFrameRate.value
        elif self.parent.minFrameRate is not None:
            frameRate = self.parent.minFrameRate.value
        self.media_segments = []
        if self.segmentTemplate.segmentTimeline:
            self.generate_segments_using_segment_timeline(frameRate)
        else:
            self.generate_segments_using_segment_template(frameRate)
        return True

    def generate_segments_using_segment_template(self, frameRate: float) -> None:
        now = self.mpd.now()
        dash_rep = self.init_segment.dash_representation
        decode_time = getattr(dash_rep, "start_time", None)
        start_number = None
        if dash_rep.segments:
            start_number = dash_rep.start_number
        seg_duration = self.segmentTemplate.duration
        if not self.attrs.check_not_none(
                seg_duration,
                'SegmentTemplate@duration is missing for a template without a SegmentTimeline element'):
            return
        if dash_rep.segments is None:
            period_duration = self.period.get_duration_as_timescale(
                dash_rep.timescale)
            num_segments = int(period_duration // seg_duration)
        else:
            # need to subtract one because dash_rep.segments also includes the init seg
            num_segments = len(dash_rep.segments) - 1
        if self.mode == 'vod':
            decode_time = self.segmentTemplate.presentationTimeOffset
            start_number = 1
        else:
            # technically, MPD@timeShiftBufferDepth is optional. When not present it
            # means depth == infinite for a live stream
            if not self.attrs.check_not_none(
                    self.mpd.timeShiftBufferDepth,
                    clause='5.3.1.2',
                    msg='MPD@timeShiftBufferDepth is required for a live stream'):
                return
            num_segments = int(
                (self.mpd.timeShiftBufferDepth.total_seconds() *
                 self.segmentTemplate.timescale) // seg_duration)
            if num_segments == 0:
                self.attrs.check_equal(
                    self.mpd.timeShiftBufferDepth.total_seconds(), 0,
                    msg='Expected MPD@timeShiftBufferDepth to equal 0 when num_segments == 0')
                return
            self.attrs.check_greater_than(
                self.mpd.timeShiftBufferDepth.total_seconds() * self.segmentTemplate.timescale,
                seg_duration,
                msg='Expected timeShiftBufferDepth to be greater than one segment')
            self.elt.check_greater_than(num_segments, 0)
            # TODO: add support for UTCTiming elements
            seg_duration_time = datetime.timedelta(
                seconds=(seg_duration / float(self.segmentTemplate.timescale)))
            # the first segment does not become available until availabilityStartTime + segment duration
            # TODO: add in Period@start value
            first_available_seg_time = now - self.mpd.timeShiftBufferDepth + seg_duration_time
            last_available_seg_time = now - seg_duration_time
            self.log.debug(
                '%s: Fragments are available from %s to %s', self.id, first_available_seg_time,
                last_available_seg_time)

            elapsed_tc = multiply_timedelta(
                last_available_seg_time - self.mpd.availabilityStartTime,
                self.segmentTemplate.timescale) - self.segmentTemplate.presentationTimeOffset
            last_fragment = self.segmentTemplate.startNumber + int(
                elapsed_tc // seg_duration)

            elapsed_tc = multiply_timedelta(
                first_available_seg_time - self.mpd.availabilityStartTime,
                self.segmentTemplate.timescale) - self.segmentTemplate.presentationTimeOffset
            start_number = self.segmentTemplate.startNumber + int(
                elapsed_tc // seg_duration)

            if start_number != (last_fragment - num_segments):
                self.log.warning(
                    '%s: Fragment range is  %d -> %d (%d segments). Expected %d segments',
                    self.id, start_number, last_fragment, last_fragment - start_number,
                    num_segments)
                num_segments = last_fragment - start_number
            if start_number < self.segmentTemplate.startNumber:
                num_segments -= self.segmentTemplate.startNumber - start_number
                if num_segments < 1:
                    num_segments = 1
                start_number = self.segmentTemplate.startNumber
            if decode_time is None:
                decode_time = (
                    (start_number - self.segmentTemplate.startNumber) *
                    seg_duration) + self.segmentTemplate.presentationTimeOffset
        self.elt.check_not_none(start_number, msg='Failed to calculate segment start number')
        self.elt.check_not_none(decode_time, msg='Failed to calculate segment decode time')
        seg_num = start_number
        tolerance = int(self.segmentTemplate.timescale // frameRate)
        self.log.debug('%s: Generating %d MediaSegments using SegmentTemplate',
                       self.id, num_segments)
        presentation_time_offset: int = self.presentation_time_offset()
        for idx in range(num_segments):
            url = self.format_url_template(
                self.segmentTemplate.media, seg_num, decode_time)
            url = urllib.parse.urljoin(self.baseurl, url)
            if idx == 0:
                tol = tolerance * 2
            elif self.parent.contentType == 'audio':
                tol = tolerance >> 1
            else:
                tol = tolerance
            ms = MediaSegment(self, url=url,
                              presentation_time_offset=presentation_time_offset,
                              expected_seg_num=seg_num, tolerance=tol,
                              expected_duration=seg_duration)
            if self.mode == 'live':
                ms.set_segment_availability(
                    seg_duration,
                    self.period.availability_start_time(),
                    self.segmentTemplate.presentationTimeOffset,
                    self.dash_timescale())
            self.media_segments.append(ms)
            seg_num += 1
            decode_time += seg_duration
        self.elt.check_greater_or_equal(
            len(self.media_segments), num_segments,
            template=r'Expected to generate {} segments, but only created {}')

    def generate_segments_using_segment_timeline(self, frameRate: float) -> None:
        timeline = self.segmentTemplate.segmentTimeline
        seg_duration = self.segmentTemplate.duration
        if seg_duration is None:
            if not self.elt.check_not_none(timeline, msg='Failed to find segment timeline'):
                return
            if not self.elt.check_greater_than(
                    len(timeline.segments), 0, msg='Failed to find any segments in timeline'):
                return
            seg_duration = timeline.duration // len(timeline.segments)
        if self.parent.contentType == 'audio':
            tolerance = self.dash_timescale() // 20
        else:
            tolerance = self.dash_timescale() // frameRate
        total_duration = 0
        self.log.debug('Generating up to %d MediaSegments using SegmentTimeline', len(timeline.segments))
        need_duration = None
        if self.target_duration is not None:
            need_duration = timedelta_to_timecode(self.target_duration, self.dash_timescale())
        presentation_time_offset: int = self.presentation_time_offset()
        for idx, seg in enumerate(timeline.segments):
            decode_time = seg.start - self.segmentTemplate.presentationTimeOffset
            if self.mode == 'vod':
                seg_num = idx + 1
            else:
                seg_num = self.segmentTemplate.startNumber + int(decode_time // seg_duration)
            expected_seg_num = None
            if '$Number$' in self.segmentTemplate.media:
                expected_seg_num = seg_num
            self.log.debug('%d: seg_num=%d decode_time=%d', idx, seg_num, decode_time)
            url = self.format_url_template(
                self.segmentTemplate.media, seg_num, decode_time)
            url = urllib.parse.urljoin(self.baseurl, url)
            ms = MediaSegment(
                self, url=url, presentation_time_offset=presentation_time_offset,
                expected_decode_time=decode_time, expected_duration=seg.duration,
                expected_seg_num=expected_seg_num, tolerance=tolerance)
            if self.mode == 'live':
                ms.set_segment_availability(
                    seg_duration, self.period.availability_start_time(),
                    self.segmentTemplate.presentationTimeOffset, self.dash_timescale())
            self.media_segments.append(ms)
            total_duration += seg.duration
            if self.mode != 'live' and need_duration and total_duration > need_duration:
                self.log.debug(
                    '%s: generated %d segments to reach requested duration %d',
                    self.id, idx + 1, need_duration)
                break
        if self.mode == 'live':
            if self.target_duration is None or self.target_duration >= self.mpd.timeShiftBufferDepth:
                tsb = self.mpd.timeShiftBufferDepth.total_seconds() * self.dash_timescale()
                self.elt.check_greater_or_equal(
                    total_duration, tsb,
                    template=r'SegmentTimeline has duration {0}, expected {1} based upon timeshiftbufferdepth')

    def presentation_time_offset(self) -> int:
        if self.segmentTemplate is None:
            return 0
        presentation_time_offset: int = self.segmentTemplate.presentationTimeOffset
        presentation_time_offset -= timedelta_to_timecode(
            self.period.start, self.segmentTemplate.timescale)
        return presentation_time_offset

    def create_init_segment_live_profile(self) -> InitSegment:
        seg_url = self.init_seg_url()
        return InitSegment(self, seg_url, None)

    def create_init_segment_on_demand_profile(self) -> InitSegment:
        if self.segmentBase and self.segmentBase.initializationList:
            url = self.baseurl
            if self.segmentBase.initializationList[0].sourceURL is not None:
                url = self.segmentBase.initializationList[0].sourceURL
            url = self.format_url_template(url)
            return InitSegment(
                self, url, self.segmentBase.initializationList[0].range)

        for sl in self.segmentList:
            if not sl.initializationList:
                continue
            if sl.initializationList[0].range is None:
                continue
            url = self.baseurl
            if sl.initializationList[0].sourceURL is not None:
                url = sl.initializationList[0].sourceURL
            url = self.format_url_template(url)
            return InitSegment(
                self, url, sl.initializationList[0].range)

        return InitSegment(self, None, None)

    async def generate_segments_on_demand_profile(self) -> bool:
        if not self.elt.check_equal(self.mode, 'odvod'):
            return False
        self.media_segments = []
        for sl in self.segmentList:
            if not sl.initializationList:
                continue
            self.elt.check_not_none(
                sl.initializationList[0].range,
                msg='HTTP range missing from first item in SegmentList')
        if not self.elt.check_not_none(
                self.init_segment.url, msg='failed to find init segment URL'):
            return False
        info = self.init_segment.dash_representation
        decode_time = info.start_time
        seg_list = []
        for sl in self.segmentList:
            seg_list += sl.segmentURLs
        if not seg_list and self.segmentBase and self.segmentBase.indexRange:
            seg_list = await self.segmentBase.load_segment_index(self.baseurl)
            decode_time = seg_list[0].decode_time
        frameRate = 24
        if self.frameRate is not None:
            frameRate = self.frameRate.value
        elif self.parent.maxFrameRate is not None:
            frameRate = self.parent.maxFrameRate.value
        elif self.parent.minFrameRate is not None:
            frameRate = self.parent.minFrameRate.value
        if self.segmentTemplate is not None:
            tolerance = self.segmentTemplate.timescale / frameRate
        else:
            tolerance = info.timescale / frameRate
        presentation_time_offset: int = self.presentation_time_offset()
        for idx, item in enumerate(seg_list):
            if not self.elt.check_not_none(
                    item.mediaRange,
                    msg=f'HTTP range for media segment {idx + 1} is missing'):
                continue
            url = self.baseurl
            if item.media is not None:
                url = item.media
            seg_num = idx + 1
            if self.parent.contentType == 'audio':
                tol = tolerance * frameRate / 2.0
            elif idx == 0:
                tol = tolerance * 2
            else:
                tol = tolerance
            dt = getattr(item, 'decode_time', decode_time)
            expected_duration = None
            if info.segments:
                expected_duration = info.segments[idx + 1].duration
            ms = MediaSegment(
                self, url=url, presentation_time_offset=presentation_time_offset,
                expected_seg_num=seg_num, expected_decode_time=dt,
                tolerance=tol, seg_range=item.mediaRange,
                expected_duration=expected_duration)
            self.media_segments.append(ms)
            if info.segments:
                # info.segments[0] is the init segment
                decode_time += info.segments[idx + 1].duration
            else:
                decode_time = None
        return True

    def num_tests(self) -> int:
        count = 0
        if ValidationFlag.REPRESENTATION in self.options.verify:
            count += 1
        if ValidationFlag.MEDIA in self.options.verify:
            count += len(self.media_segments)
        return count

    def children(self) -> list[DashElement]:
        rv = super().children() + self.media_segments
        if self.init_segment is not None:
            rv.append(self.init_segment)
        if self.contentProtection:
            rv += self.contentProtection
        return rv

    def finished(self) -> bool:
        if self.progress.aborted():
            return True
        if ValidationFlag.MEDIA not in self.options.verify:
            return self._validated
        total_dur = self.get_validated_duration()
        if self.target_duration is None:
            if self.mode != 'live' and total_dur.total_seconds() > 0:
                return True
            return False
        self.log.debug('%s: Total media duration %s, need %s %s',
                       self.unique_id(), total_dur, self.target_duration,
                       total_dur >= self.target_duration)
        return total_dur >= self.target_duration

    def get_validated_duration(self) -> datetime.timedelta:
        """
        Get the amount of time (in timescale units) that has been checked
        """
        total_dur = 0
        for seg in self.media_segments:
            if seg.validated:
                if seg.duration is not None:
                    total_dur += seg.duration
                    # self.log.debug(
                    #    '%s: seg[%s] duration=%d total=%d', self.id,
                    #    seg.name, seg.duration, total_dur)
                elif seg.expected_duration is not None:
                    total_dur += seg.expected_duration
                    # self.log.debug(
                    #    '%s: seg[%s] expected_duration=%d total=%d', self.id,
                    #    seg.name, seg.expected_duration, total_dur)
        return timecode_to_timedelta(total_dur, self.dash_timescale())

    def get_codec(self) -> str | None:
        if self.init_segment is not None:
            return self.init_segment.codecs
        return None

    async def validate(self) -> None:
        if self.progress.aborted():
            return
        futures: set[Awaitable] = set()
        if ValidationFlag.REPRESENTATION in self.options.verify:
            futures.add(super().validate())
            futures.add(self.validate_self())
        if ValidationFlag.MEDIA in self.options.verify:
            futures.add(self.init_segment.validate())
        await asyncio.gather(*futures)
        self.progress.inc()
        self._validated = True
        if ValidationFlag.MEDIA not in self.options.verify:
            return
        if len(self.media_segments) == 0:
            return
        next_decode_time = None
        next_seg_num = None
        total_dur = 0
        if self.target_duration is None:
            need_duration = None
        else:
            need_duration = timedelta_to_timecode(self.target_duration, self.dash_timescale())
        dash_timescale = self.dash_timescale()
        media_timescale = self.init_segment.media_timescale()
        for idx, seg in enumerate(self.media_segments):
            self.log.debug(
                '%s[%d]: num=%s time=%s', self.id, idx, next_seg_num, next_decode_time)
            if self.progress.aborted():
                return
            self.progress.text(seg.url)
            if seg.expected_seg_num is None and next_seg_num is not None:
                seg.expected_seg_num = next_seg_num
            elif seg.expected_seg_num != next_seg_num:
                next_decode_time = None
            if (
                    seg.expected_decode_time is None and
                    next_decode_time is not None and
                    self.mode != 'odvod'):
                seg_index = seg.expected_seg_num - self.segmentTemplate.startNumber
                expected_time = (
                    seg_index * self.segmentTemplate.duration *
                    media_timescale // dash_timescale)
                msg = f'Based upon segment number {seg.expected_seg_num} the expected '
                msg += f'decode_time={expected_time} but next_decode_time={next_decode_time} '
                msg += f'({next_decode_time - expected_time})'
                if seg.expected_duration is not None:
                    delta = seg.expected_duration // 2
                else:
                    delta = media_timescale
                seg.elt.check_almost_equal(
                    expected_time, next_decode_time, delta=delta, msg=msg)
                seg.expected_decode_time = next_decode_time
            if not seg.validated:
                await seg.validate()
            self.log.debug('%s: Segment %s decode time span: %s -> %s', self.id,
                           seg.name, seg.decode_time, seg.next_decode_time)
            next_decode_time = seg.next_decode_time
            if seg.seg_num is None:
                next_seg_num = None
            else:
                next_seg_num = seg.seg_num + 1
            if seg.duration is not None:
                total_dur += seg.duration
            if need_duration is not None and total_dur >= need_duration:
                self.log.debug(
                    '%s: reached required validation duration %d',
                    self.id, need_duration)
                break

    async def validate_self(self) -> None:
        if self.progress.aborted():
            return
        if self.mode != 'odvod':
            self.elt.check_not_none(
                self.segmentTemplate,
                msg=f'SegmentTemplate is required when using DASH profiles {self.mpd.profiles}')
            self.elt.check_not_none(
                self.segmentTemplate.initialization,
                msg='SegmentTemplate@initialization is missing')
        self.elt.check_not_none(self.baseurl, msg='Failed to find BaseURL')
        self.elt.check_not_none(self.init_segment)
        self.elt.check_not_none(self.media_segments)
        if self.mode != "live":
            msg = ('Failed to generate any segments for Representation ' +
                   f'{self.unique_id()} for MPD {self.mpd.url}')
            self.elt.check_greater_than(len(self.media_segments), 0, msg=msg)
        self.attrs.check_not_none(
            self.bandwidth, msg='bandwidth is a mandatory attribute', clause='5.3.5.2')
        self.attrs.check_not_none(
            self.id, msg='id is a mandatory attribute', clause='5.3.5.2')
        self.attrs.check_not_none(
            self.mimeType, msg='Representation@mimeType is a mandatory attribute',
            clause='5.3.7.2')
        if ValidationFlag.MEDIA in self.options.verify:
            moov = await self.init_segment.get_moov()
            if not self.elt.check_not_none(moov, msg=f'{self.id}: Failed to find MOOV data'):
                self.log.warning('%s: Failed to get MOOV box from init segment %s', self.id,
                                 self.init_segment.name)
                return
        if self.options.encrypted:
            if self.options.ivsize is None:
                self.options.ivsize = self.init_segment.dash_representation.iv_size
            if self.contentProtection:
                cp_elts = self.contentProtection
            else:
                cp_elts = self.parent.contentProtection
            if self.parent.contentType == 'video':
                self.elt.check_greater_than(
                    len(cp_elts), 0,
                    msg='An encrypted stream must have ContentProtection elements')
                found = False
                for elt in cp_elts:
                    if (elt.schemeIdUri == "urn:mpeg:dash:mp4protection:2011" and
                            elt.value == "cenc"):
                        found = True
                self.elt.check_true(
                    found, None, None,
                    msg="DASH CENC ContentProtection element not found")
        else:
            # parent ContentProtection elements checked in parent's validate()
            self.elt.check_equal(
                len(self.contentProtection), 0,
                msg='ContentProtection elements should not be present for unencrypted stream')
        self.progress.inc()
        if self.progress.aborted():
            return
        if self.mode == "odvod":
            self.check_on_demand_profile()
        else:
            self.check_live_profile()

    def check_live_profile(self):
        self.elt.check_not_none(
            self.segmentTemplate,
            msg='SegmentTemplate is required element')
        if self.mode == 'vod':
            return
        if not self.elt.check_equal(self.mode, 'live'):
            return
        if self.mpd.timeShiftBufferDepth is None:
            # missing MPD@timeShiftBufferDepth error is reported by manifest.py
            return
        seg_duration = self.segmentTemplate.duration
        timeline = self.segmentTemplate.segmentTimeline
        timescale = self.segmentTemplate.timescale
        decode_time: int | None = None
        if seg_duration is None:
            if not self.elt.check_not_none(timeline, msg='SegmentTimeline missing'):
                return
            seg_duration = timeline.duration / float(len(timeline.segments))
        if timeline is not None:
            num_segments = len(self.segmentTemplate.segmentTimeline.segments)
            decode_time = timeline.segments[0].start
        else:
            num_segments = math.floor(self.mpd.timeShiftBufferDepth.total_seconds() *
                                      timescale / seg_duration)
            num_segments = int(num_segments)
            num_segments = min(num_segments, 25)
        now = self.mpd.now()
        elapsed_time = now - self.period.availability_start_time()
        startNumber = self.segmentTemplate.startNumber
        last_fragment = startNumber + int(
            scale_timedelta(elapsed_time, timescale, seg_duration))
        first_fragment = last_fragment - math.floor(
            self.mpd.timeShiftBufferDepth.total_seconds() * timescale / seg_duration)
        if first_fragment < startNumber:
            num_segments -= startNumber - first_fragment
            if num_segments < 1:
                num_segments = 1
            first_fragment = startNumber
        if decode_time is None:
            decode_time = (first_fragment - startNumber) * seg_duration
        self.elt.check_not_none(decode_time, msg='Failed to calculate decode time')
        pos = (self.mpd.availabilityStartTime +
               datetime.timedelta(seconds=(decode_time / float(timescale))))
        self.elt.check_less_than(
            pos, now, template=r'Pos {0} is after current time of day {1}')

    def check_on_demand_profile(self):
        pass

    URL_TEMPLATE_RE = re.compile(r'\$(Bandwidth|Number|RepresentationID|Time)(%0\d+d)?\$')

    def format_url_template(self, url: str, seg_num: int = 0, decode_time: int = 0) -> str:
        """
        Replaces the template variables according the DASH template syntax
        """
        def repfn(matchobj) -> str:
            value = params[matchobj.group(1)]
            fmt = matchobj.group(2)
            if fmt is None:
                return f'{value}'
            fmt = r'{0' + fmt.replace('%', ':') + r'}'
            return fmt.format(value)
        params = {
            'RepresentationID': self.ID,
            'Bandwidth': self.bandwidth,
            'Number': seg_num,
            'Time': decode_time,
            '': '$',
        }
        return self.URL_TEMPLATE_RE.sub(repfn, url)

    def dash_timescale(self) -> int:
        """
        The timescale (in units per seconds) as defined by the data
        in the Manifest. Note this might not match the timescale of
        the actual media fragments!
        """
        if self.segmentTemplate and self.segmentTemplate.timescale:
            return self.segmentTemplate.timescale
        info = self.init_segment.dash_representation
        if info is not None and info.timescale:
            return info.timescale
        return 1
