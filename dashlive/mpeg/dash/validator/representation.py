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
    UTC
)

from .dash_element import DashElement
from .init_segment import InitSegment
from .media_segment import MediaSegment
from .multiple_segment_base_type import MultipleSegmentBaseType
from .representation_base_type import RepresentationBaseType

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
        if self.segmentTemplate is None:
            self.segmentTemplate = parent.segmentTemplate
        if self.mode == "odvod":
            segmentBase = elt.findall('./dash:SegmentBase', self.xmlNamespaces)
            self.elt.check_less_than(len(segmentBase), 2)
            if len(segmentBase):
                self.segmentBase = MultipleSegmentBaseType(
                    segmentBase[0], self)

    def generate_segment_todo_list(self) -> None:
        if self.mode == "odvod":
            self.generate_segments_on_demand_profile()
        else:
            self.generate_segments_live_profile()
        self.progress.inc()

    def set_representation_info(self, info: ServerRepresentation):
        self.info = info

    def load_representation_info(self) -> bool:
        if not self.elt.check_not_none(
                self.init_segment, msg='Failed to find init segment'):
            return False
        if self.init_segment.atoms is None:
            if not self.init_segment.load():
                return False
        parsed = urllib.parse.urlparse(self.init_seg_url())
        filename = PurePath(parsed.path)
        self.info = ServerRepresentation.load(filename.name, self.init_segment.atoms)
        self.info.segments = None
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

    def generate_segments_live_profile(self) -> None:
        if not self.elt.check_not_equal(self.mode, 'odvod'):
            return
        if not self.elt.check_not_none(
                self.segmentTemplate,
                msg='SegmentTemplate is required when using live profile'):
            self.init_segment = InitSegment(self, None, None)
            return
        self.init_segment = InitSegment(self, self.init_seg_url(), None)
        if self.info is None:
            self.load_representation_info()
        if not self.elt.check_not_none(self.info, msg='Failed to get Representation info'):
            return
        decode_time = getattr(self.info, "start_time", None)
        start_number = None
        if self.info.segments:
            start_number = self.info.start_number
        self.media_segments = []
        timeline = self.segmentTemplate.segmentTimeline
        seg_duration = self.segmentTemplate.duration
        if seg_duration is None:
            if not self.elt.check_not_none(timeline, msg='Failed to find segment timeline'):
                return
            if not self.elt.check_greater_than(
                    len(timeline.segments), 0, msg='Failed to find any segments in timeline'):
                return
            seg_duration = timeline.duration // len(timeline.segments)
        if timeline is None:
            if self.info.segments is not None:
                # need to subtract one because self.info.segments also includes the init seg
                num_segments = len(self.info.segments) - 1
            else:
                period_duration = self.parent.parent.get_duration_as_timescale(
                    self.info.timescale)
                num_segments = int(period_duration // seg_duration)
        else:
            num_segments = len(timeline.segments)
            decode_time = timeline.segments[0].start
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
                self.mpd.timeShiftBufferDepth.total_seconds(),
                seg_duration / float(self.segmentTemplate.timescale))
            self.elt.check_greater_than(num_segments, 0)
            now = datetime.datetime.now(tz=UTC())
            # TODO: add support for UTCTiming elements
            elapsed_time = now - self.mpd.availabilityStartTime
            elapsed_tc = multiply_timedelta(
                elapsed_time, self.segmentTemplate.timescale)
            elapsed_tc -= self.segmentTemplate.presentationTimeOffset
            last_fragment = self.segmentTemplate.startNumber + int(
                elapsed_tc // seg_duration)
            # first_fragment = last_fragment - math.floor(
            #    self.mpd.timeShiftBufferDepth.total_seconds() * self.segmentTemplate.timescale /
            #    seg_duration)
            if start_number is None:
                start_number = last_fragment - num_segments
            if start_number < self.segmentTemplate.startNumber:
                num_segments -= self.segmentTemplate.startNumber - start_number
                if num_segments < 1:
                    num_segments = 1
                start_number = self.segmentTemplate.startNumber
            if decode_time is None:
                decode_time = (
                    (start_number - self.segmentTemplate.startNumber) *
                    seg_duration)
        self.elt.check_not_none(start_number, msg='Failed to calculate segment start number')
        self.elt.check_not_none(decode_time, msg='Failed to calculate segment decode time')
        if self.options.duration:
            max_num_segments = int(
                self.options.duration *
                self.segmentTemplate.timescale //
                seg_duration)
            num_segments = min(num_segments, max_num_segments)
        seg_num = start_number
        frameRate = 24
        if self.frameRate is not None:
            frameRate = self.frameRate.value
        elif self.parent.maxFrameRate is not None:
            frameRate = self.parent.maxFrameRate.value
        elif self.parent.minFrameRate is not None:
            frameRate = self.parent.minFrameRate.value
        if self.segmentTemplate is not None:
            tolerance = int(self.segmentTemplate.timescale // frameRate)
        else:
            tolerance = int(self.info.timescale // frameRate)
        if self.options.duration is None:
            num_segments = min(num_segments, 20)
        self.log.debug('Generating %d MediaSegments', num_segments)
        if timeline is not None:
            msg = r'Expected segment segmentTimeline to have at least {} items, found {}'.format(
                num_segments, len(timeline.segments))
            self.elt.check_greater_or_equal(len(timeline.segments), num_segments, msg=msg)
        for idx in range(num_segments):
            url = self.format_url_template(
                self.segmentTemplate.media, seg_num, decode_time)
            url = urllib.parse.urljoin(self.baseurl, url)
            if self.parent.contentType == 'audio':
                tol = tolerance * frameRate / 2.0
            elif idx == 0:
                tol = tolerance * 2
            else:
                tol = tolerance
            ms = MediaSegment(self, url, seg_num=seg_num,
                              decode_time=decode_time,
                              tolerance=tol)
            self.media_segments.append(ms)
            seg_num += 1
            if timeline is not None:
                decode_time += timeline.segments[idx].duration
            else:
                decode_time = None
            if self.options.duration is not None:
                if decode_time is None:
                    dt = seg_num * seg_duration
                else:
                    dt = decode_time
                if dt >= (self.options.duration * self.segmentTemplate.timescale):
                    return
        self.elt.check_greater_or_equal(
            len(self.media_segments), num_segments,
            template=r'Expected to generate {} segments, but only created {}')

    def generate_segments_on_demand_profile(self):
        if not self.elt.check_equal(self.mode, 'odvod'):
            return
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
            return
        if self.info is None:
            self.load_representation_info()
        if not self.elt.check_not_none(self.info, msg='Failed to get Representation init segment'):
            return
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
            timescale = self.segmentTemplate.timescale
        else:
            tolerance = self.info.timescale / frameRate
            timescale = self.info.timescale
        for idx, item in enumerate(seg_list):
            if not self.elt.check_not_none(
                    item.mediaRange,
                    msg=f'HTTP range for media segment {idx + 1} is missing'):
                continue
            url = self.baseurl
            if item.media is not None:
                url = item.media
            seg_num = idx + 1
            # if idx == 0 and self.segmentTemplate and self.segmentTemplate.segmentTimeline:
            #    seg_num = None
            if self.parent.contentType == 'audio':
                tol = tolerance * frameRate / 2.0
            elif idx == 0:
                tol = tolerance * 2
            else:
                tol = tolerance
            dt = getattr(item, 'decode_time', decode_time)
            ms = MediaSegment(self, url, seg_num=seg_num,
                              decode_time=dt, tolerance=tol,
                              seg_range=item.mediaRange)
            self.media_segments.append(ms)
            if self.info.segments:
                # self.info.segments[0] is the init segment
                decode_time += self.info.segments[idx + 1].duration
            else:
                decode_time = None
            if self.options.duration is not None:
                if decode_time >= (self.options.duration * timescale):
                    return

    def num_tests(self, depth: int = -1) -> int:
        if depth == 0:
            return 0
        return 1 + len(self.media_segments)

    def children(self) -> list[DashElement]:
        rv = super().children() + self.media_segments
        if self.init_segment is not None:
            rv.append(self.init_segment)
        if self.contentProtection:
            rv += self.contentProtection
        return rv

    def validate(self, depth: int = -1) -> None:
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
        self.attrs.check_not_none(self.bandwidth, msg='bandwidth is a mandatory attribute')
        self.attrs.check_not_none(self.id, msg='id is a mandatory attribute')
        self.attrs.check_not_none(
            self.mimeType, msg='Representation@mimeType is a mandatory attribute',
            clause='5.3.7.2')
        if self.info is None:
            if not self.load_representation_info():
                return
        if depth > 0:
            self.init_segment.validate(depth - 1)
        moov = self.init_segment.get_moov()
        if not self.elt.check_not_none(moov, msg='Failed to find MOOV data'):
            self.log.warning('Failed to validate init segment')
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
        if depth == 0 or self.progress.aborted():
            return
        if self.mode == "odvod":
            self.check_on_demand_profile()
        else:
            self.check_live_profile()
        if len(self.media_segments) == 0:
            return
        next_decode_time = self.media_segments[0].decode_time
        # next_seg_num = self.media_segments[0].seg_num
        self.log.debug('starting next_decode_time: %s', str(next_decode_time))
        for seg in self.media_segments:
            if self.progress.aborted():
                return
            if seg.decode_time is None:
                msg = f'{seg.url_description()}: Failed to calculate next decode time for segment {seg.seg_num}'
                if not self.elt.check_not_none(next_decode_time, msg=msg):
                    self.progress.inc()
                    break
                seg.decode_time = next_decode_time
            else:
                msg = (f'{seg.url_description()}: expected decode time {next_decode_time} ' +
                       f'for segment {seg.seg_num} but got {seg.decode_time}')
                self.elt.check_equal(next_decode_time, seg.decode_time, msg=msg)
                next_decode_time = seg.decode_time
            self.progress.text(seg.url)
            moof = seg.validate(depth - 1)
            msg = f'Failed to fetch MOOF {seg.url_description()}'
            if not self.elt.check_not_none(moof, msg=msg):
                self.log.warning(msg)
                continue
            if seg.seg_num is None:
                seg.seg_num = moof.mfhd.sequence_number
            # next_seg_num = seg.seg_num + 1
            for sample in moof.traf.trun.samples:
                if not sample.duration:
                    sample.duration = moov.mvex.trex.default_sample_duration
                next_decode_time += sample.duration
            self.log.debug('Segment time span: %d -> %d', seg.decode_time, next_decode_time)
            self.progress.inc()

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
        now = datetime.datetime.now(tz=UTC())
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

    def format_url_template(self, url, seg_num=0, decode_time=0):
        """
        Replaces the template variables according the DASH template syntax
        """
        def repfn(matchobj, value):
            if isinstance(value, str):
                return value
            fmt = matchobj.group(1)
            if fmt is None:
                if isinstance(value, str):
                    fmt = r'%s'
                else:
                    fmt = r'%d'
            fmt = '{0' + fmt.replace('%', ':') + '}'
            return fmt.format(value)
        for name, value in [('RepresentationID', self.ID),
                            ('Bandwidth', self.bandwidth),
                            ('Number', seg_num),
                            ('Time', decode_time),
                            ('', '$')]:
            rx = re.compile(fr'\${name}(%0\d+d)?\$')
            url = rx.sub(lambda match: repfn(match, value), url)
        return url
