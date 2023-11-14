#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import datetime
import math
import re
from pathlib import PurePath
from typing import Optional
import urllib.parse

from lxml import etree as ET

from dashlive.mpeg.dash.representation import Representation as ServerRepresentation
from dashlive.utils.date_time import (
    multiply_timedelta,
    scale_timedelta,
)

from .dash_element import DashElement
from .init_segment import InitSegment
from .media_segment import MediaSegment
from .multiple_segment_base_type import MultipleSegmentBaseType
from .representation_base_type import RepresentationBaseType
from .validation_flag import ValidationFlag

class Representation(RepresentationBaseType):
    attributes = RepresentationBaseType.attributes + [
        ('bandwidth', int, None),
        ('id', str, None),
        ('qualityRanking', int, None),
        ('dependencyId', str, None),
    ]

    def __init__(self, elt: ET.ElementBase, parent: DashElement) -> None:
        super().__init__(elt, parent)
        self.info: ServerRepresentation | None = None
        self.init_segment: Optional[InitSegment] = None
        self.media_segments: list[MediaSegment] = []
        self.segmentBase: Optional[MultipleSegmentBaseType] = None
        self._validated = False
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

    async def merge_previous_element(self, prev: "Representation") -> bool:
        self.log.debug('Merging previous representation %s', prev.id)
        if prev.init_segment is not None:
            self.init_segment = prev.init_segment
            self.log.debug(
                '%s: Reusing previous init segment. has_atoms=%s',
                self.id, self.init_segment.atoms is not None)
        self.info = prev.info
        await self.generate_segment_todo_list()
        seg_map = {}
        for seg in prev.media_segments:
            seg_map[seg.name] = seg
        merged_segments = []
        for seg in self.media_segments:
            try:
                merged_segments.append(seg_map[seg.name])
                self.log.debug(
                    '%s: Re-use existing media segment %s', self.id, seg.name)
            except KeyError as err:
                self.log.debug('%s: Adding new media segment %s (%s)',
                               self.id, seg.name, err)
                merged_segments.append(seg)
        self.media_segments = merged_segments
        return True

    async def generate_segment_todo_list(self) -> bool:
        if self.mode == "odvod":
            rv = await self.generate_segments_on_demand_profile()
        else:
            rv = await self.generate_segments_live_profile()
        self.progress.inc()
        return rv

    def set_representation_info(self, info: ServerRepresentation):
        self.info = info

    async def load_representation_info(self) -> bool:
        if not self.elt.check_not_none(
                self.init_segment, msg='Failed to find init segment'):
            return False
        if self.init_segment.atoms is None:
            self.log.debug('%s: Loading init segment', self.id)
            if not await self.init_segment.load():
                return False
        parsed = urllib.parse.urlparse(self.init_seg_url())
        filename = PurePath(parsed.path)
        self.info = ServerRepresentation.load(filename.name, self.init_segment.atoms)
        self.info.segments = None
        self.info.start_time = None
        return True

    def init_seg_url(self) -> str:
        if self.mode == 'odvod':
            return self.format_url_template(self.baseurl)
        self.elt.check_not_none(self.segmentTemplate, msg='SegmentTemplate missing')
        self.elt.check_not_none(
            self.segmentTemplate.initialization,
            msg='SegmentTemplate failed to find initialization URL')
        url = self.format_url_template(self.segmentTemplate.initialization)
        return urllib.parse.urljoin(self.baseurl, url)

    async def generate_segments_live_profile(self) -> bool:
        if not self.elt.check_not_equal(self.mode, 'odvod'):
            return False
        if not self.elt.check_not_none(
                self.segmentTemplate,
                msg='SegmentTemplate is required when using live profile'):
            self.init_segment = InitSegment(self, None, None)
            return False
        if self.init_segment is None:
            self.init_segment = InitSegment(self, self.init_seg_url(), None)
        if self.info is None:
            await self.load_representation_info()
        if not self.elt.check_not_none(self.info, msg='Failed to get Representation info'):
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
        decode_time = getattr(self.info, "start_time", None)
        start_number = None
        if self.info.segments:
            start_number = self.info.start_number
        seg_duration = self.segmentTemplate.duration
        if not self.attrs.check_not_none(
                seg_duration,
                'SegmentTemplate@duration is missing for a template without a SegmentTimeline element'):
            return
        if self.info.segments is None:
            period_duration = self.parent.parent.get_duration_as_timescale(
                self.info.timescale)
            num_segments = int(period_duration // seg_duration)
        else:
            # need to subtract one because self.info.segments also includes the init seg
            num_segments = len(self.info.segments) - 1
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
            ms = MediaSegment(self, url, expected_seg_num=seg_num, tolerance=tol,
                              expected_duration=seg_duration)
            if self.mode == 'live':
                ms.set_segment_availability(
                    seg_duration, self.segmentTemplate.presentationTimeOffset, self.timescale())
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
            tolerance = self.timescale() // 20
        else:
            tolerance = self.timescale() // frameRate
        total_duration = 0
        self.log.debug('Generating %d MediaSegments using SegmentTimeline', len(timeline.segments))
        for idx, seg in enumerate(timeline.segments):
            decode_time = seg.start - self.segmentTemplate.presentationTimeOffset
            if self.mode == 'vod':
                seg_num = idx + 1
            else:
                seg_num = self.segmentTemplate.startNumber + int(decode_time // seg_duration)
            self.log.debug('%d: seg_num=%d decode_time=%d', idx, seg_num, decode_time)
            url = self.format_url_template(
                self.segmentTemplate.media, seg_num, decode_time)
            url = urllib.parse.urljoin(self.baseurl, url)
            ms = MediaSegment(
                self, url, expected_decode_time=decode_time, expected_duration=seg.duration,
                tolerance=tolerance)
            if self.mode == 'live':
                ms.set_segment_availability(
                    seg_duration, self.segmentTemplate.presentationTimeOffset, self.timescale())
            self.media_segments.append(ms)
            total_duration += seg.duration
        if self.mode == 'live':
            tsb = self.mpd.timeShiftBufferDepth.total_seconds() * self.timescale()
            if (
                    self.options.duration is None or
                    self.options.duration >= self.mpd.timeShiftBufferDepth.total_seconds()):
                self.elt.check_greater_or_equal(
                    total_duration, tsb,
                    template=r'SegmentTimeline has duration {0}, expected {1} based upon timeshiftbufferdepth')

    async def generate_segments_on_demand_profile(self) -> bool:
        if not self.elt.check_equal(self.mode, 'odvod'):
            return False
        self.media_segments = []
        self.init_segment = None
        if self.segmentBase and self.segmentBase.initializationList:
            url = self.baseurl
            if self.segmentBase.initializationList[0].sourceURL is not None:
                url = self.segmentBase.initializationList[0].sourceURL
            url = self.format_url_template(url)
            self.init_segment = InitSegment(
                self, url, self.segmentBase.initializationList[0].range)
        for sl in self.segmentList:
            if not sl.initializationList:
                continue
            self.elt.check_not_none(
                sl.initializationList[0].range,
                msg='HTTP range missing from first item in SegmentList')
            url = self.baseurl
            if sl.initializationList[0].sourceURL is not None:
                url = sl.initializationList[0].sourceURL
            url = self.format_url_template(url)
            self.init_segment = InitSegment(
                self, url, sl.initializationList[0].range)
        if not self.elt.check_not_none(self.init_segment, msg='failed to find init segment URL'):
            return False
        if self.info is None:
            if not await self.load_representation_info():
                return False
        if not self.elt.check_not_none(self.info, msg='Failed to get Representation init segment'):
            return False
        decode_time = self.info.start_time
        seg_list = []
        for sl in self.segmentList:
            seg_list += sl.segmentURLs
        if not seg_list and self.segmentBase and self.segmentBase.indexRange:
            seg_list = self.segmentBase.load_segment_index(self.baseurl)
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
            tolerance = self.info.timescale / frameRate
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
            if self.info.segments:
                expected_duration = self.info.segments[idx + 1].duration
            ms = MediaSegment(
                self, url, expected_seg_num=seg_num, expected_decode_time=dt,
                tolerance=tol, seg_range=item.mediaRange,
                expected_duration=expected_duration)
            self.media_segments.append(ms)
            if self.info.segments:
                # self.info.segments[0] is the init segment
                decode_time += self.info.segments[idx + 1].duration
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
        if ValidationFlag.MEDIA not in self.options.verify:
            return self._validated
        total_dur = 0
        for seg in self.media_segments:
            if seg.validated and seg.duration is not None:
                total_dur += seg.duration
        if self.mode != 'live' and total_dur > 0:
            return True
        if self.options.duration is None:
            return False
        need_duration = self.options.duration * self.timescale()
        self.log.debug('%s: Total media duration %d, need %d',
                       self.id, total_dur, need_duration)
        return total_dur >= need_duration

    async def validate(self) -> None:
        if ValidationFlag.REPRESENTATION in self.options.verify:
            await self.validate_self()
            self.progress.inc()
            self._validated = True
        if len(self.media_segments) == 0:
            return
        if ValidationFlag.MEDIA not in self.options.verify:
            return
        next_decode_time = None
        next_seg_num = None
        total_dur = 0
        if self.options.duration is None:
            need_duration = None
        else:
            need_duration = self.options.duration * self.timescale()
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
            if seg.expected_decode_time is None and next_decode_time is not None:
                expected_time = seg.expected_seg_num - self.segmentTemplate.startNumber
                expected_time *= self.segmentTemplate.duration
                msg = f'Based upon segment number {seg.expected_seg_num} the expected '
                msg += f'decode_time={expected_time} but next_decode_time={next_decode_time} '
                msg += f'({next_decode_time - expected_time})'
                if seg.expected_duration is not None:
                    delta = seg.expected_duration // 2
                else:
                    delta = self.timescale()
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
                return

    async def validate_self(self) -> None:
        if self.progress.aborted():
            return
        if self.segmentTemplate is None:
            self.elt.check_equal(
                self.mode, 'odvod',
                msg='SegmentTemplate is required when using DASH profile')
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
        if self.info is None:
            if not await self.load_representation_info():
                return
        if ValidationFlag.MEDIA in self.options.verify:
            await self.init_segment.validate()
            moov = await self.init_segment.get_moov()
            if not self.elt.check_not_none(moov, msg=f'{self.id}: Failed to find MOOV data'):
                self.log.warning('%s: Failed to get MOOV box from init segment %s', self.id,
                                 self.init_segment.name)
                return
        if self.options.encrypted:
            if self.options.ivsize is None:
                self.options.ivsize = self.info.iv_size
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
        seg_duration = self.segmentTemplate.duration
        timeline = self.segmentTemplate.segmentTimeline
        timescale = self.segmentTemplate.timescale
        decode_time = None
        if seg_duration is None:
            if not self.elt.check_not_none(timeline, msg='SegmentTimeline missing'):
                return
            seg_duration = timeline.duration / float(len(timeline.segments))
        if timeline is not None:
            num_segments = len(self.segmentTemplate.segmentTimeline.segments)
            decode_time = timeline.segments[0].start
        else:
            if not self.attrs.check_not_none(
                    self.mpd.timeShiftBufferDepth,
                    msg='MPD@timeShiftBufferDepth is a required attribute for a live stream'):
                return
            num_segments = math.floor(self.mpd.timeShiftBufferDepth.total_seconds() *
                                      timescale / seg_duration)
            num_segments = int(num_segments)
            num_segments = min(num_segments, 25)
        now = self.mpd.now()
        elapsed_time = now - self.mpd.availabilityStartTime
        startNumber = self.segmentTemplate.startNumber
        # TODO: subtract Period@start
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
        earliest_pos = (now - self.mpd.timeShiftBufferDepth -
                        datetime.timedelta(seconds=(seg_duration / float(timescale))))
        self.elt.check_greater_or_equal(
            pos,
            earliest_pos,
            msg=f'Position {pos} is before first available fragment time {earliest_pos}')
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

    def timescale(self) -> int:
        if self.info:
            if self.info.timescale:
                return self.info.timescale
        if self.segmentTemplate:
            if self.segmentTemplate.timescale:
                return self.segmentTemplate.timescale
        return 1
