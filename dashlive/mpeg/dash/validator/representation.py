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
import urllib.parse

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

    def __init__(self, rep, parent):
        super().__init__(rep, parent)
        if self.segmentTemplate is None:
            self.segmentTemplate = parent.segmentTemplate
        if self.segmentTemplate is None:
            self.elt.check_equal(self.mode, 'odvod')
        self.elt.check_not_none(self.baseurl, msg='Failed to find BaseURL')
        if self.mode == "odvod":
            segmentBase = rep.findall('./dash:SegmentBase', self.xmlNamespaces)
            self.elt.check_less_than(len(segmentBase), 2)
            if len(segmentBase):
                self.segmentBase = MultipleSegmentBaseType(
                    segmentBase[0], self)
            else:
                self.segmentBase = None
            self.generate_segments_on_demand_profile()
        else:
            self.generate_segments_live_profile()
        self.elt.check_not_none(self.init_segment)
        self.elt.check_not_none(self.media_segments)
        if self.mode != "live":
            msg = ('Failed to generate any segments for Representation ' +
                   f'{self.unique_id()} for MPD {self.mpd.url}')
            self.elt.check_greater_than(len(self.media_segments), 0, msg=msg)

    def init_seg_url(self):
        if self.mode == 'odvod':
            return self.format_url_template(self.baseurl)
        self.elt.check_not_none(self.segmentTemplate)
        self.elt.check_not_none(self.segmentTemplate.initialization)
        url = self.format_url_template(self.segmentTemplate.initialization)
        return urllib.parse.urljoin(self.baseurl, url)

    def generate_segments_live_profile(self) -> None:
        if not self.elt.check_not_equal(self.mode, 'odvod'):
            return
        info = self.validator.get_representation_info(self)
        if not self.elt.check_not_none(info, msg='Failed to get Representation info'):
            return
        decode_time = getattr(info, "decode_time", None)
        start_number = getattr(info, "start_number", None)
        self.media_segments = []
        if not self.elt.check_not_none(
                self.segmentTemplate,
                msg='SegmentTemplate is required when using on-demand profile'):
            self.init_segment = InitSegment(self, None, info, None)
            return
        self.init_segment = InitSegment(self, self.init_seg_url(), info, None)
        timeline = self.segmentTemplate.segmentTimeline
        seg_duration = self.segmentTemplate.duration
        if seg_duration is None:
            if not self.elt.check_not_none(timeline, msg='Failed to find segment timeline'):
                return
            if not self.elt.check_greater_than(
                    len(timeline.segments), 0, msg='Failed to find any segments in timeline'):
                return
            seg_duration = timeline.duration // len(timeline.segments)
        if self.mode == 'vod':
            if not self.elt.check_not_none(info.num_segments):
                return
            num_segments = info.num_segments
            decode_time = self.segmentTemplate.presentationTimeOffset
            start_number = 1
        else:
            if timeline is not None:
                num_segments = len(timeline.segments)
                if decode_time is None:
                    decode_time = timeline.segments[0].start
            else:
                if not self.attrs.check_not_none(
                        self.mpd.timeShiftBufferDepth,
                        msg='MPD@timeShiftBufferDepth is required for a live stream'):
                    return
                num_segments = int(
                    (self.mpd.timeShiftBufferDepth.total_seconds() *
                     self.segmentTemplate.timescale) // seg_duration)
                if num_segments == 0:
                    self.attrs.check_equal(self.mpd.timeShiftBufferDepth.total_seconds(), 0)
                    return
                self.attrs.check_greater_than(
                    self.mpd.timeShiftBufferDepth.total_seconds(),
                    seg_duration / float(self.segmentTemplate.timescale))
                self.elt.check_greater_than(num_segments, 0)
                if self.options.duration:
                    max_num_segments = (
                        self.options.duration *
                        self.segmentTemplate.timescale //
                        seg_duration)
                    num_segments = min(num_segments, max_num_segments)
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
                    start_number - self.segmentTemplate.startNumber) * seg_duration
        self.elt.check_not_none(start_number, msg='Failed to calculate segment start number')
        self.elt.check_not_none(decode_time, msg='Failed to calculate segment decode time')
        seg_num = start_number
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
            ms = MediaSegment(self, url, info, seg_num=seg_num,
                              decode_time=decode_time,
                              tolerance=tol, seg_range=None)
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
        self.media_segments = []
        self.init_segment = None
        info = self.validator.get_representation_info(self)
        if not self.elt.check_not_none(info, msg='Failed to get Representation info'):
            return
        decode_time = None
        if info.segments:
            decode_time = 0
        if self.segmentBase and self.segmentBase.initializationList:
            url = self.baseurl
            if self.segmentBase.initializationList[0].sourceURL is not None:
                url = self.segmentBase.initializationList[0].sourceURL
            url = self.format_url_template(url)
            self.init_segment = InitSegment(
                self, url, info,
                self.segmentBase.initializationList[0].range)
        seg_list = []
        for sl in self.segmentList:
            if sl.initializationList:
                self.elt.check_not_none(
                    sl.initializationList[0].range,
                    msg='HTTP range missing from first item in SegmentList')
                url = self.baseurl
                if sl.initializationList[0].sourceURL is not None:
                    url = sl.initializationList[0].sourceURL
                url = self.format_url_template(url)
                self.init_segment = InitSegment(
                    self, url, info, sl.initializationList[0].range)
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
            tolerance = info.timescale / frameRate
            timescale = info.timescale
        for idx, item in enumerate(seg_list):
            self.elt.check_not_none(
                item.mediaRange,
                msg=f'HTTP range for media segment {idx + 1} is missing')
            url = self.baseurl
            if item.media is not None:
                url = item.media
            seg_num = idx + 1
            if idx == 0 and self.segmentTemplate and self.segmentTemplate.segmentTimeline:
                seg_num = None
            if self.parent.contentType == 'audio':
                tol = tolerance * frameRate / 2.0
            elif idx == 0:
                tol = tolerance * 2
            else:
                tol = tolerance
            dt = getattr(item, 'decode_time', decode_time)
            ms = MediaSegment(self, url, info, seg_num=seg_num,
                              decode_time=dt, tolerance=tol,
                              seg_range=item.mediaRange)
            self.media_segments.append(ms)
            if info.segments:
                decode_time += info.segments[idx + 1]['duration']
            if self.options.duration is not None:
                if decode_time >= (self.options.duration * timescale):
                    return

    def num_tests(self, depth: int = -1) -> int:
        if depth == 0:
            return 0
        return 1 + len(self.media_segments)

    def children(self) -> list[DashElement]:
        rv = super().children() + self.media_segments + [self.init_segment]
        if self.contentProtection:
            rv += self.contentProtection
        return rv

    def validate(self, depth: int = -1) -> None:
        self.attrs.check_not_none(self.bandwidth, msg='bandwidth is a mandatory attribute')
        self.attrs.check_not_none(self.id, msg='id is a mandatory attribute')
        self.attrs.check_not_none(
            self.mimeType, msg='Representation@mimeType is a mandatory attribute',
            clause='5.3.7.2')
        info = self.validator.get_representation_info(self)
        if info.moov is None:
            info.moov = self.init_segment.validate(depth - 1)
            self.validator.set_representation_info(self, info)
        if not self.elt.check_not_none(info.moov, msg='Failed to find MOOV data'):
            return
        if self.options.encrypted:
            if self.options.ivsize is None:
                try:
                    avc = info.moov.trak.mdia.minf.stbl.stsd.encv
                except AttributeError:
                    avc = info.moov.trak.mdia.minf.stbl.stsd.enca
                self.options.ivsize = avc.sinf.schi.tenc.iv_size
                info.ivsize = self.options.ivsize
                self.log.info('Discovered IV size is %d', info.ivsize * 8)
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
            seg.set_info(info)
            if seg.decode_time is None:
                if not self.elt.check_not_none(next_decode_time):
                    self.progress.inc()
                    break
                seg.decode_time = next_decode_time
            else:
                self.elt.check_equal(
                    next_decode_time, seg.decode_time,
                    msg=f'{seg.url}: expected decode time {next_decode_time} but got {seg.decode_time}')
                next_decode_time = seg.decode_time
            if seg.seg_range is None and seg.url in info.tested_media_segment:
                next_decode_time = seg.next_decode_time
                continue
            self.progress.text(seg.url)
            moof = seg.validate(depth - 1)
            if not self.elt.check_not_none(moof, msg='Failed to fetch MOOF'):
                continue
            if seg.seg_num is None:
                seg.seg_num = moof.mfhd.sequence_number
            # next_seg_num = seg.seg_num + 1
            for sample in moof.traf.trun.samples:
                if not sample.duration:
                    sample.duration = info.moov.mvex.trex.default_sample_duration
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
