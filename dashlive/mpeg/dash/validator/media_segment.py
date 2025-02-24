#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import datetime
import io
from pathlib import Path
from typing import Optional
import urllib.parse

from dashlive.mpeg import mp4
from dashlive.utils.date_time import timecode_to_timedelta, to_iso_datetime

from .dash_element import DashElement
from .events import InbandEventStream
from .http_range import HttpRange

class MediaSegment(DashElement):
    expected_decode_time: int | None
    expected_seg_num: int | None
    expected_duration: int | None
    presentation_time_offset: int  # manifest timescale units
    seg_range: HttpRange | None
    tolerance: int
    url: str

    def __init__(self,
                 parent: DashElement,
                 url: str,
                 presentation_time_offset: int,
                 tolerance: int,
                 expected_duration: int | None,
                 expected_seg_num: int | None = None,
                 expected_decode_time: int | None = None,
                 seg_range: Optional[HttpRange] = None) -> None:
        super().__init__(None, parent)
        assert url is not None
        assert presentation_time_offset is not None
        self.url = url
        self.presentation_time_offset = presentation_time_offset
        self.expected_decode_time = expected_decode_time
        self.expected_seg_num = expected_seg_num
        self.expected_duration = expected_duration
        self.tolerance = tolerance
        self.seg_range = seg_range
        self.duration: int | None = None
        self.validated = False
        self.decode_time: int | None = None
        self.seg_num: int | None = None
        self.next_decode_time: int | None = None
        self.availability_start_time: datetime.datetime | None = None
        self.availability_end_time: datetime.datetime | None = None
        path = Path(urllib.parse.urlparse(url).path)
        if self.parent.id is not None:
            self.name = f'{self.parent.id}:{path.name}'
        else:
            self.name = path.name
        if seg_range:
            self.name += f'?range={self.seg_range}'
        self.elt.prefix = f'{self.name}: '
        self.log.debug(
            'MediaSegment: url=%s $Number$=%s $Time$=%s tolerance=%d',
            url, str(expected_seg_num), str(expected_decode_time), tolerance)

    def children(self) -> list[DashElement]:
        return []

    def set_segment_availability(self,
                                 segment_duration: int,
                                 period_availability_start: datetime.datetime,
                                 presentationTimeOffset: int,
                                 timescale: int) -> None:
        decode_time = self.expected_decode_time
        if decode_time is None:
            decode_time = (
                self.expected_seg_num - self.parent.segmentTemplate.startNumber) * segment_duration
        delta = timecode_to_timedelta(
            decode_time + segment_duration - presentationTimeOffset,
            timescale)
        self.availability_start_time = period_availability_start + delta
        self.availability_end_time = self.availability_start_time + self.mpd.timeShiftBufferDepth
        self.availability_end_time += timecode_to_timedelta(segment_duration, timescale)
        self.log.debug('Segment availability %s -> %s',
                       to_iso_datetime(self.availability_start_time),
                       to_iso_datetime(self.availability_end_time))

    async def validate(self) -> None:
        await self.validate_segment()
        self.progress.inc()

    async def validate_segment(self) -> None:
        now: datetime.datetime = self.mpd.now()
        if self.availability_start_time and self.availability_start_time > now:
            log = ''
            if self.expected_seg_num:
                log = f'num={self.expected_seg_num} '
            elif self.expected_decode_time:
                log = f'time={self.expected_decode_time} '
            self.log.debug(
                '%s: Segment %s not yet available. availability_start_time=%s',
                self.name, log, self.availability_start_time)
            return
        self.validated = True
        discard_before: datetime.datetime = now + datetime.timedelta(seconds=2)
        if self.availability_end_time and self.availability_end_time < discard_before:
            self.log.debug(
                '%s: Segment is no longer available. Expired at %s',
                self.name, self.availability_end_time)
            return
        headers = None
        if self.seg_range is not None:
            headers = {"Range": f"bytes={self.seg_range}"}
        # self.log.debug('MediaSegment: url=%s headers=%s', self.url, headers)
        response = await self.http.get(self.url, headers=headers)
        # self.log.debug('Status: %d  Length: %s', response.status_code,
        #               response.headers['Content-Length'])
        if self.progress.aborted():
            return
        if self.seg_range is None:
            if not self.elt.check_equal(
                    response.status_code, 200,
                    msg=f'Missing segment {self.url}: {response.status_code}'):
                return
        else:
            if not self.elt.check_equal(
                    response.status_code, 206,
                    msg=f'Incorrect HTTP status code for RANGE GET {self.url}: {response.status_code}'):
                return
        if self.parent.mimeType is not None:
            self.elt.check_starts_with(
                response.headers['Content-Type'], self.parent.mimeType,
                template=r'HTTP Content-Type "{0}" should match Representation MIME type "{1}"')
        async with self.pool.group(self.progress) as tg:
            body = response.get_data(as_text=False)
            if self.options.save:
                tg.submit(self.save, body)
            parse_task = tg.submit(self.parse_data, body)
        moof = parse_task.result()
        if not self.elt.check_not_none(
                moof, msg='Failed to find MOOF box'):
            return
        self.seg_num = moof.mfhd.sequence_number
        self.decode_time = moof.traf.tfdt.base_media_decode_time
        info = self.parent.init_segment.dash_representation
        if info.encrypted:
            self.check_saio_offset(moof)
        else:
            self.elt.check_not_in(
                'senc', moof.traf,
                msg='senc box should not be found in a clear stream')

        self.log.debug(
            '%s: seg_num=%d (expected %s) base_media_decode_time=%d (expected %s)',
            self.name, moof.mfhd.sequence_number, self.expected_seg_num,
            moof.traf.tfdt.base_media_decode_time, self.expected_decode_time)
        if self.expected_seg_num is not None:
            self.elt.check_equal(
                self.expected_seg_num, moof.mfhd.sequence_number,
                template=r'Sequence number error, expected {0}, got {1}')
        if self.expected_decode_time is not None:
            tc_diff = moof.traf.tfdt.base_media_decode_time - self.expected_decode_time
            tc_delta = timecode_to_timedelta(
                tc_diff, self.parent.dash_timescale()).total_seconds()
            msg = (
                f'Decode time {self.decode_time} should ' +
                f'be {self.expected_decode_time} ({tc_diff}) [{tc_delta} seconds]')
            self.elt.check_almost_equal(
                self.expected_decode_time,
                self.decode_time,
                delta=self.tolerance,
                msg=msg)
        moov = await self.parent.init_segment.get_moov()
        if not self.elt.check_not_none(
                moov, msg='Failed to get MOOV box from init segment'):
            return
        pts_values: set[int] = set()
        dts: int = moof.traf.tfdt.base_media_decode_time
        for sample in moof.traf.trun.samples:
            try:
                pts = dts + sample.composition_time_offset
            except AttributeError:
                pts = dts
            pts -= self.presentation_time_offset
            # TODO: some PTS values in first segment might be < zero
            self.elt.check_greater_or_equal(pts, 0)
            self.elt.check_not_in(pts, pts_values)
            pts_values.add(pts)
            if sample.duration is None:
                samp_dur = moov.mvex.trex.default_sample_duration
            else:
                samp_dur = sample.duration
            dts += samp_dur
        # self.log.debug('Last sample duration %d', samp_dur)
        self.duration = dts - moof.traf.tfdt.base_media_decode_time
        self.next_decode_time = dts

        # Special case - the timescale of media segments doesn't have to be
        # the same as the timescale listed in the manifest :(
        media_timescale: int | None = self.parent.init_segment.media_timescale()
        dash_timescale: int = self.parent.dash_timescale()
        if media_timescale == 0 or dash_timescale == 0:
            self.elt.add_error(
                f'Neither DASH timescale {dash_timescale} nor media timescale ' +
                f'{media_timescale} can be zero')
            return
        if media_timescale != dash_timescale and media_timescale not in {None, 0}:
            self.duration = int(self.duration * dash_timescale // media_timescale)

        if self.expected_duration is not None:
            self.elt.check_almost_equal(
                self.expected_duration, self.duration,
                delta=self.parent.dash_timescale(),
                msg=f'Expected duration {self.expected_duration} but duration is {self.duration}')
        self.log.debug('Segment %d duration %d. Next expected DTS %d',
                       self.seg_num, self.duration, dts)

    def save(self, body: bytes) -> None:
        if self.parent.id:
            default = f'media-{self.parent.id}-{self.parent.id}-{self.seg_num}'
        else:
            default = f'media-{self.parent.id}-{self.parent.bandwidth}-{self.seg_num}'
        filename = self.output_filename(
            default=default, bandwidth=self.parent.bandwidth,
            prefix=self.options.prefix, elt_id=self.parent.id)
        self.log.debug('saving media segment: %s', filename)
        with self.open_file(filename, self.options) as dest:
            dest.write(body)

    def parse_data(self, body: bytes) -> mp4.Mp4Atom | None:
        src = io.BytesIO(body)
        options = {"strict": True, "lazy_load": True, "mode": "r"}
        info = self.parent.init_segment.dash_representation
        if self.options.encrypted:
            msg = 'Expected an encrypted stream, but fragment is not encrypted'
        else:
            msg = 'Expected a clear stream, but fragment is encrypted'
        # Only require the encryption of video AdaptationSet to match options.encrypted
        if self.parent.parent.contentType == 'video':
            self.elt.check_equal(self.options.encrypted, info.encrypted, msg=msg)
        elif info.encrypted and not self.options.encrypted:
            self.elt.check_equal(self.options.encrypted, info.encrypted, msg=msg)
        if info.encrypted:
            if not self.elt.check_not_none(
                    info.iv_size, msg='IV size is unknown'):
                return
            options["iv_size"] = info.iv_size
        atoms = mp4.Mp4Atom.load(src, options=options, use_wrapper=True)
        self.elt.check_greater_than(len(atoms), 1)
        try:
            moof = atoms.moof
        except AttributeError:
            self.elt.add_error('MOOF box missing from media segment')
            return
        try:
            mdat = atoms.mdat
        except AttributeError:
            self.elt.add_error('MDAT box missing from media segment')
            return
        try:
            self.check_emsg_box(atoms.emsg)
        except AttributeError:
            pass
        first_sample_pos = moof.traf.tfhd.base_data_offset + moof.traf.trun.data_offset
        last_sample_end = first_sample_pos
        for samp in moof.traf.trun.samples:
            last_sample_end += samp.size
        msg = (
            'trun.data_offset must point inside the MDAT box. ' +
            f'trun points to {first_sample_pos} but first sample of ' +
            f'MDAT is at {mdat.position + mdat.header_size}. ' +
            f'trun last sample is {last_sample_end}. End of ' +
            f'MDAT is {mdat.position + mdat.size}. ' +
            f'tfhd.base_data_offset={moof.traf.tfhd.base_data_offset} and ' +
            f'trun.data_offset={moof.traf.trun.data_offset}'
        )
        self.elt.check_equal(
            first_sample_pos, mdat.position + mdat.header_size, msg=msg)
        self.elt.check_less_than_or_equal(
            last_sample_end, mdat.position + mdat.size, msg=msg)
        return moof

    def check_emsg_box(self, emsg):
        found = False
        for evs in self.parent.event_streams:
            self.log.debug('Found schemeIdUri="%s", value="%s"',
                           evs.schemeIdUri, evs.value)
            if (evs.schemeIdUri == emsg.scheme_id_uri and
                    evs.value == emsg.value):
                self.elt.check_is_instance(evs, InbandEventStream)
                found = True
        for evs in self.parent.parent.event_streams:
            self.log.debug('Found schemeIdUri="%s", value="%s"',
                           evs.schemeIdUri, evs.value)
            if (evs.schemeIdUri == emsg.scheme_id_uri and
                    evs.value == emsg.value):
                self.elt.check_is_instance(evs, InbandEventStream)
                found = True
        self.elt.check_true(
            found, emsg.scheme_id_uri, emsg.value,
            template=r'Failed to find an InbandEventStream with schemeIdUri="{}" value="{}"')

    def check_saio_offset(self, moof: mp4.Mp4Atom) -> None:
        try:
            senc = moof.traf.senc
        except AttributeError:
            self.elt.add_error(
                'An encrypted stream must contain a senc box')
            return
        saio = moof.traf.find_child('saio')
        self.elt.check_not_none(
            saio, msg='saio box is required for an encrypted stream')
        self.elt.check_equal(
            len(saio.offsets), 1,
            msg='saio box should only have one offset entry')
        tfhd = moof.traf.find_child('tfhd')
        if tfhd is None:
            base_data_offset = moof.position
        else:
            base_data_offset = tfhd.base_data_offset
        sample_pos = senc.position + senc.samples[0].offset
        msg = (
            r'saio.offsets[0] should point to first ' +
            r'CencSampleAuxiliaryData entry. ' +
            f'Expected {sample_pos}, ' +
            f'got {saio.offsets[0] + base_data_offset}')
        self.elt.check_equal(
            sample_pos, saio.offsets[0] + base_data_offset, msg=msg)
        self.elt.check_equal(len(moof.traf.trun.samples), len(senc.samples))
