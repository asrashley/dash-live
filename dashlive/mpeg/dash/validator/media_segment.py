#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Optional
import urllib.parse

from dashlive.mpeg import mp4
from dashlive.utils.buffered_reader import BufferedReader

from .dash_element import DashElement
from .events import InbandEventStream
from .http_range import HttpRange

class MediaSegment(DashElement):
    def __init__(self, parent: DashElement, url: str, seg_num: int,
                 decode_time: int | None, tolerance: int,
                 seg_range: Optional[HttpRange] = None) -> None:
        super().__init__(None, parent)
        self.seg_num = seg_num
        self.decode_time = decode_time
        self.tolerance = tolerance
        self.seg_range = seg_range
        self.url = url
        self.log.debug('MediaSegment: url=%s $Number$=%s $Time$=%s tolerance=%d',
                       url, str(seg_num), str(decode_time), tolerance)

    def children(self) -> list[DashElement]:
        return []

    def url_description(self) -> str:
        path = urllib.parse.urlparse(self.url).path
        if self.seg_range:
            return f'{path}?range={self.seg_range}'
        return path

    def validate(self, depth: int = -1,
                 all_atoms: bool = False) -> mp4.Mp4Atom | list[mp4.Mp4Atom] | None:
        headers = None
        if self.seg_range is not None:
            headers = {"Range": f"bytes={self.seg_range}"}
        self.log.debug('MediaSegment: url=%s headers=%s', self.url, headers)
        response = self.http.get(self.url, headers=headers)
        self.log.debug('Status: %d  Length: %s', response.status_code,
                       response.headers['Content-Length'])
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
                response.headers['content-type'], self.parent.mimeType,
                template=r'HTTP Content-Type "{0}" should match Representation MIME type "{1}"')
        if self.options.save:
            default = f'media-{self.parent.id}-{self.parent.bandwidth}-{self.seg_num}'
            filename = self.output_filename(
                default, self.parent.bandwidth, prefix=self.options.prefix)
            self.log.debug('saving media segment: %s', filename)
            with self.open_file(filename, self.options) as dest:
                dest.write(response.body)
        src = BufferedReader(None, data=response.get_data(as_text=False))
        options = {"strict": True}
        info = self.parent.info
        self.elt.check_equal(self.options.encrypted, info.encrypted)
        if info.encrypted:
            if not self.elt.check_not_none(
                    info.iv_size, msg='IV size is unknown'):
                return
            options["iv_size"] = info.iv_size
        atoms = mp4.Mp4Atom.load(src, options=options)
        self.elt.check_greater_than(len(atoms), 1)
        moof = None
        mdat = None
        self.log.debug('MediaSegment atoms=%s',
                       [a.atom_type for a in atoms])
        for a in atoms:
            if a.atom_type == 'emsg':
                self.check_emsg_box(a)
            elif a.atom_type == 'moof':
                moof = a
            elif a.atom_type == 'mdat':
                mdat = a
                self.elt.check_not_none(
                    moof,
                    msg='Failed to find moof box before mdat box')
        if not self.elt.check_not_none(
                moof, msg='Failed to find MOOF box'):
            return
        if not self.elt.check_not_none(
                mdat, msg='Failed to find mdat box'):
            return
        if info.encrypted:
            self.check_saio_offset(moof)
        else:
            self.elt.check_not_in(
                'senc', moof.traf,
                msg='senc box should not be found in a clear stream')
        if self.seg_num is not None:
            self.elt.check_equal(
                moof.mfhd.sequence_number, self.seg_num,
                msg='Sequence number error, expected {}, got {}'.format(
                    self.seg_num, moof.mfhd.sequence_number))
        if self.decode_time is not None:
            self.log.debug(
                'decode_time=%s base_media_decode_time=%d delta=%d',
                str(self.decode_time),
                moof.traf.tfdt.base_media_decode_time,
                abs(moof.traf.tfdt.base_media_decode_time - self.decode_time))
            seg_dt = moof.traf.tfdt.base_media_decode_time
            msg = 'Decode time {seg_dt:d} should be {dt:d} for segment {num} in {url:s}'.format(
                seg_dt=seg_dt, dt=self.decode_time, num=self.seg_num, url=self.url_description())
            self.elt.check_almost_equal(
                seg_dt,
                self.decode_time,
                delta=self.tolerance,
                msg=msg)
        first_sample_pos = moof.traf.tfhd.base_data_offset + moof.traf.trun.data_offset
        last_sample_end = first_sample_pos
        for samp in moof.traf.trun.samples:
            last_sample_end += samp.size
        msg = ' '.join([
            r'trun.data_offset must point inside the MDAT box.',
            r'trun points to {} but first sample of MDAT is {}'.format(
                first_sample_pos, mdat.position + mdat.header_size),
            r'trun last sample is {} but end of MDAT is {}'.format(
                last_sample_end, mdat.position + mdat.size),
        ])
        self.elt.check_greater_or_equal(
            first_sample_pos, mdat.position + mdat.header_size, msg=msg)
        self.elt.check_less_than_or_equal(
            last_sample_end, mdat.position + mdat.size, msg=msg)
        self.elt.check_equal(first_sample_pos, mdat.position + mdat.header_size, msg=msg)
        moov = self.parent.init_segment.get_moov()
        if not self.elt.check_not_none(
                moov, msg='Failed to get MOOV box from init segment'):
            return
        pts_values = set()
        dts = moof.traf.tfdt.base_media_decode_time
        for sample in moof.traf.trun.samples:
            try:
                pts = dts + sample.composition_time_offset
            except AttributeError:
                pts = dts
            self.elt.check_not_in(pts, pts_values)
            pts_values.add(pts)
            if sample.duration is None:
                dts += moov.mvex.trex.default_sample_duration
            else:
                dts += sample.duration
        self.duration = dts - moof.traf.tfdt.base_media_decode_time
        if all_atoms:
            return atoms
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
        msg = (
            r'saio.offsets[0] should point to first ' +
            r'CencSampleAuxiliaryData entry. ' +
            f'Expected {senc.samples[0].position}, ' +
            f'got {saio.offsets[0] + base_data_offset}')
        self.elt.check_equal(
            senc.samples[0].position, saio.offsets[0] + base_data_offset,
            msg=msg)
        self.elt.check_equal(len(moof.traf.trun.samples), len(senc.samples))
