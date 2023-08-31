#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from dashlive.mpeg import mp4
from dashlive.utils.buffered_reader import BufferedReader

from .dash_element import DashElement
from .events import InbandEventStream
from .exceptions import MissingSegmentException

class MediaSegment(DashElement):
    def __init__(self, parent, url, info, seg_num,
                 decode_time, tolerance, seg_range):
        super().__init__(None, parent)
        self.info = info
        self.seg_num = seg_num
        self.decode_time = decode_time
        self.tolerance = tolerance
        self.seg_range = seg_range
        self.url = url
        self.log.debug('MediaSegment: url=%s $Number$=%s $Time$=%s tolerance=%d',
                       url, str(seg_num), str(decode_time), tolerance)

    def set_info(self, info):
        self.info = info

    def validate(self, depth: int = -1, all_atoms: bool = False) -> None:
        headers = None
        if self.seg_range is not None:
            headers = {"Range": f"bytes={self.seg_range}"}
        self.log.debug('MediaSegment: url=%s headers=%s', self.url, headers)
        response = self.http.get(self.url, headers=headers)
        if self.seg_range is None:
            if response.status_code != 200:
                raise MissingSegmentException(self.url, response)
        else:
            if response.status_code != 206:
                raise MissingSegmentException(self.url, response)
        if self.parent.mimeType is not None:
            if self.options.strict:
                self.checkStartsWith(response.headers['content-type'],
                                     self.parent.mimeType)
        if self.options.save:
            default = f'media-{self.parent.id}-{self.parent.bandwidth}-{self.seg_num}'
            filename = self.output_filename(
                default, self.parent.bandwidth, prefix=self.options.prefix)
            self.log.debug('saving media segment: %s', filename)
            with self.open_file(filename, self.options) as dest:
                dest.write(response.body)
        src = BufferedReader(None, data=response.get_data(as_text=False))
        options = {"strict": True}
        self.checkEqual(self.options.encrypted, self.info.encrypted)
        if self.info.encrypted:
            options["iv_size"] = self.info.iv_size
        atoms = mp4.Mp4Atom.load(src, options=options)
        self.checkGreaterThan(len(atoms), 1)
        moof = None
        mdat = None
        for a in atoms:
            if a.atom_type == 'emsg':
                self.check_emsg_box(a)
            elif a.atom_type == 'moof':
                moof = a
            elif a.atom_type == 'mdat':
                mdat = a
                self.checkIsNotNone(
                    moof,
                    msg='Failed to find moof box before mdat box')
        self.checkIsNotNone(moof)
        self.checkIsNotNone(mdat)
        try:
            senc = moof.traf.senc
            self.checkNotEqual(
                self.info.encrypted, False,
                msg='senc box should not be found in a clear stream')
            saio = moof.traf.find_child('saio')
            self.checkIsNotNone(
                saio,
                msg='saio box is required for an encrypted stream')
            self.checkEqual(
                len(saio.offsets), 1,
                msg='saio box should only have one offset entry')
            tfhd = moof.traf.find_child('tfhd')
            if tfhd is None:
                base_data_offset = moof.position
            else:
                base_data_offset = tfhd.base_data_offset
            self.checkEqual(
                senc.samples[0].position,
                saio.offsets[0] + base_data_offset,
                msg=(r'saio.offsets[0] should point to first CencSampleAuxiliaryData entry. ' +
                     'Expected {}, got {}'.format(
                         senc.samples[0].position, saio.offsets[0] + base_data_offset)))
            self.checkEqual(len(moof.traf.trun.samples), len(senc.samples))
        except AttributeError:
            self.checkNotEqual(
                self.info.encrypted, True,
                msg='Failed to find senc box in encrypted stream')
        if self.seg_num is not None:
            self.checkEqual(moof.mfhd.sequence_number, self.seg_num,
                            msg='Sequence number error, expected {}, got {}'.format(
                                self.seg_num, moof.mfhd.sequence_number))
        moov = self.info.moov
        if self.decode_time is not None:
            self.log.debug(
                'decode_time=%s base_media_decode_time=%d delta=%d',
                str(self.decode_time),
                moof.traf.tfdt.base_media_decode_time,
                abs(moof.traf.tfdt.base_media_decode_time - self.decode_time))
            seg_dt = moof.traf.tfdt.base_media_decode_time
            msg = 'Decode time {seg_dt:d} should be {dt:d} for segment {num} in {url:s}'.format(
                seg_dt=seg_dt, dt=self.decode_time, num=self.seg_num, url=self.url)
            self.checkAlmostEqual(
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
        self.checkGreaterThanOrEqual(first_sample_pos, mdat.position + mdat.header_size, msg)
        self.checkLessThanOrEqual(last_sample_end, mdat.position + mdat.size, msg)
        if self.options.strict:
            self.checkEqual(first_sample_pos, mdat.position + mdat.header_size, msg)
        pts_values = set()
        dts = moof.traf.tfdt.base_media_decode_time
        for sample in moof.traf.trun.samples:
            try:
                pts = dts + sample.composition_time_offset
            except AttributeError:
                pts = dts
            self.checkNotIn(pts, pts_values)
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
                self.checkIsInstance(evs, InbandEventStream)
                found = True
        for evs in self.parent.parent.event_streams:
            self.log.debug('Found schemeIdUri="%s", value="%s"',
                           evs.schemeIdUri, evs.value)
            if (evs.schemeIdUri == emsg.scheme_id_uri and
                    evs.value == emsg.value):
                self.checkIsInstance(evs, InbandEventStream)
                found = True
        self.checkTrue(
            found,
            'Failed to find an InbandEventStream with schemeIdUri="{}" value="{}"'.format(
                emsg.scheme_id_uri, emsg.value))
