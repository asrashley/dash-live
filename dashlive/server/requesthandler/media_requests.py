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
import io
import logging

import flask

from dashlive.mpeg import mp4
from dashlive.mpeg.dash.adaptation_set import AdaptationSet
from dashlive.mpeg.dash.representation import Representation
from dashlive.mpeg.dash.timing import DashTiming
from dashlive.server import models
from dashlive.server.events.factory import EventFactory
from dashlive.server.options.container import OptionsContainer
from dashlive.utils.date_time import UTC
from dashlive.utils.buffered_reader import BufferedReader

from .base import RequestHandlerBase
from .decorators import (
    uses_stream,
    uses_media_file,
    current_media_file,
    current_stream
)
from .drm_context import DrmContext
from .utils import add_allowed_origins

class OnDemandMedia(RequestHandlerBase):
    """
    Handler that returns media fragments for the on-demand profile.
    This handler does not support adding PSSH boxes into the init segment.
    """

    decorators = [uses_stream, uses_media_file]

    def get(self, stream: str, filename: str, ext: str) -> flask.Response:
        try:
            start, end, status, headers = self.get_http_range(current_media_file.blob.size)
        except ValueError as ve:
            logging.warning('Invalid HTTP range: %s', ve)
            return flask.make_response('Invalid HTTP range', 400)
        if start is None:
            logging.warning('HTTP range not specified')
            return flask.make_response('HTTP range must be specified', 400)
        if ext == 'm4a':
            headers['Content-Type'] = 'audio/mp4'
        elif ext == 'm4v':
            headers['Content-Type'] = 'video/mp4'
        else:
            headers['Content-Type'] = 'application/mp4'
        data = b''
        if status == 206:
            with current_media_file.open_file(start=start) as reader:
                data = reader.read(1 + end - start)
        return flask.make_response((data, status, headers))


# blobstore_handlers.BlobstoreDownloadHandler):
class LiveMedia(RequestHandlerBase):
    """
    Handler that returns media fragments using the DASH live profile.
    This handler can be used for both on-demand and live streams, as
    the DASH live profile supports both use cases.
    """

    decorators = [uses_stream, uses_media_file]

    def get(self, mode: str, stream: str, filename: str,
            ext: str,
            segment_num: str | None = None,
            segment_time: int | None = None) -> flask.Response:
        seg_num: int | None = None

        logging.debug(
            'LiveMedia.get: %s.%s stream=%s num=%s time=%s',
            filename, ext, stream, segment_num, segment_time)
        representation = current_media_file.representation
        try:
            options = self.calculate_options(mode, flask.request.args, current_stream)
        except ValueError as err:
            logging.error('Invalid CGI parameters: %s', err)
            return flask.make_response('Invalid CGI parameters', 400)
        if current_stream.timing_reference is None:
            logging.warning('stream.timing_reference has not been configured')
            return flask.make_response(
                'stream.timing_reference has not been configured', 404)
        if representation.encrypted and not options.encrypted:
            logging.warning('Request for an encrypted stream, when drmSelection is empty')
            return flask.make_response(
                'Request for an encrypted stream, when drmSelection is empty', 404)
        options.update(segmentTimeline=(segment_time is not None))
        mf = current_media_file
        if mf.content_type not in {'audio', 'video', 'text'}:
            return flask.make_response(
                f'Unsupported content_type {mf.content_type}', 404)
        adp_set = AdaptationSet(
            mode=options.mode, content_type=mf.content_type, id=mf.track_id,
            segment_timeline=options.segmentTimeline)
        adp_set.representations.append(current_media_file.representation)
        adp_set.compute_av_values()
        headers = {
            'Accept-Ranges': 'bytes',
            'Content-Type': adp_set.mimeType,
        }
        add_allowed_origins(headers)
        if segment_num == 'init':
            return self.generate_init_segment(mode, adp_set, headers, options)

        try:
            if segment_num is not None:
                seg_num = int(segment_num, 10)
        except ValueError as err:
            logging.warning('Invalid segment number: %s', err)
            return flask.make_response('Invalid segment number', 404)

        return self.generate_media_segment(
            mode, adp_set, headers, options, seg_num, segment_time)

    def generate_init_segment(
            self,
            mode: str,
            adp_set: AdaptationSet,
            headers: dict[str, str | int],
            options: OptionsContainer) -> flask.Response:
        mf = current_media_file
        representation = mf.representation

        err = self.check_for_synthetic_http_error(mf.content_type, 0, options)
        if err is not None:
            return err

        atom = self.load_fragment(representation, 0, options)
        if representation.encrypted:
            keys = models.Key.get_kids(representation.kids)
            drms = DrmContext(current_stream, keys, options)
            for drm in drms:
                if drm.moov is not None:
                    pssh = drm.moov(representation.default_kid)
                    atom.moov.append_child(pssh)
        if mode == 'live':
            try:
                # remove the mehd box as this stream is not supposed to
                # have a fixed duration
                del atom.moov.mehd
            except AttributeError:
                pass
        data = atom.encode()
        return flask.make_response((data, 200, headers))

    def generate_media_segment(
            self,
            mode: str,
            adp_set: AdaptationSet,
            headers: dict[str, str | int],
            options: OptionsContainer,
            seg_num: int | None,
            segment_time: int | None = None) -> flask.Response:
        mod_segment: int = 0
        mf = current_media_file
        representation = mf.representation

        err = self.check_for_synthetic_http_error(mf.content_type, seg_num, options)
        if err is not None:
            return err

        now = datetime.datetime.now(tz=UTC())
        timing = DashTiming(now, current_stream.timing_reference, options)
        adp_set.set_dash_timing(timing)
        try:
            first_fragment, last_fragment = representation.calculate_first_and_last_segment_number()
            logging.debug('elapsedTime=%s firstFragment=%d lastFragment=%d',
                          timing.elapsedTime, first_fragment, last_fragment)
            seg_num, mod_segment, origin_time = representation.calculate_segment_number_and_time(
                segment_time, seg_num)
            logging.debug('segment=%d mod=%d origin=%d', seg_num, mod_segment, origin_time)
        except ValueError as err:
            logging.warning('ValueError: %s', err)
            logging.info(
                'Segment %d not found (valid range= %d -> %d)',
                seg_num, first_fragment, last_fragment)
            return flask.make_response('Segment not found', 404)

        if seg_num < first_fragment or seg_num > last_fragment:
            logging.info(
                '%s: Request for fragment %d that is not available (%d -> %d)',
                now, seg_num, first_fragment, last_fragment)
            if mode == 'live':
                first_tc = timing.availabilityStartTime + datetime.timedelta(
                    seconds=(first_fragment * representation.segment_duration /
                             representation.timescale))
                logging.debug('oldest fragment %d start = %s', first_fragment, first_tc)
            return flask.make_response(
                f'Segment {seg_num} not found (valid range= {first_fragment}->{last_fragment})',
                404)

        assert mod_segment >= 0 and mod_segment <= representation.num_media_segments

        atom = self.load_fragment(
            representation, mod_segment, options,
            parse_samples=(adp_set.content_type == 'video' and options.videoCorruption))

        moof_modified: bool = False
        traf_modified: bool = False

        moof: mp4.Mp4Atom = atom.moof
        traf: mp4.Mp4Atom = moof.traf

        if mode == 'live':
            tfdt: mp4.Mp4Atom
            try:
                tfdt = traf.tfdt
            except AttributeError as err:
                logging.debug('Adding tfdt box to traf: %s', err)
                base_media_decode_time: int
                base_media_decode_time = sum([
                    seg.duration for seg in representation.segments[1:mod_segment]])
                tfdt = mp4.TrackFragmentDecodeTimeBox(
                    version=0, flags=0,
                    base_media_decode_time=base_media_decode_time)
                tfhd_index = atom.moof.traf.index('tfhd')
                traf.insert_child(tfhd_index + 1, tfdt)
                traf_modified = True
                moof_modified = True
                # force trun box to have a data_offset field, as its
                # position will have changed
                traf.trun.flags |= mp4.TrackFragmentRunBox.data_offset_present

            tfdt.base_media_decode_time += origin_time

            # Update the sequenceNumber field in the MovieFragmentHeader
            # box
            moof.mfhd.sequence_number = seg_num
            diff = None
            if segment_time is not None:
                diff = segment_time - tfdt.base_media_decode_time
                logging.debug(
                    r'%s: $Time$ want=%s got=%d (%s)',
                    mf.name, segment_time, tfdt.base_media_decode_time, diff)
            logging.debug(
                r'%s: origin=%d duration=%d',
                mf.name, origin_time, representation.segment_duration)

        try:
            # remove any sidx box as it has a baseMediaDecodeTime and it's
            # an optional index
            del atom.sidx
        except AttributeError:
            pass

        if adp_set.content_type == 'video':
            event_generators = EventFactory.create_event_generators(options)
            if event_generators:
                logging.debug('creating emsg boxes')
                moof_idx = atom.index('moof')
                for evgen in event_generators:
                    boxes = evgen.create_emsg_boxes(
                        moof=atom.moof,
                        adaptation_set=adp_set,
                        segment_num=seg_num,
                        mod_segment=mod_segment,
                        representation=representation)
                    # the emsg boxes must be inserted before the
                    # moof box (see DASH section 5.10.3.3)
                    for idx, emsg in enumerate(boxes):
                        atom.children.insert(moof_idx + idx, emsg)
                        moof_modified = True
        if representation.encrypted:
            traf_modified = self.update_traf_if_required(options, traf)
            moof_modified = moof_modified or traf_modified
        if moof_modified:
            tfhd = traf.find_child('tfhd')
            if tfhd is not None:
                # force base_data_offset to be re-calculated when the
                # tfhd box is encoded
                tfhd.base_data_offset = None
        if traf_modified:
            saio = traf.find_child('saio')
            senc = traf.find_child('senc')
            if saio is not None and senc is not None:
                # force re-calculation of SAIO offset to SENC box
                saio.offsets = None
        dest = io.BytesIO()
        atom.encode(dest)
        if mf.content_type == 'video' and options.videoCorruption:
            self.apply_video_corruption(representation, seg_num, atom, dest, options)
        data = dest.getvalue()
        status = 200
        try:
            start, end, status, range_headers = self.get_http_range(len(data))
            if start is not None:
                data = data[start:end + 1]
            headers.update(range_headers)
        except (ValueError) as ve:
            return flask.make_response(f'{ve}', 400)
        return flask.make_response((data, status, headers))

    @staticmethod
    def load_fragment(representation: Representation,
                      seg_index: int,
                      options: OptionsContainer,
                      parse_samples: bool = False) -> mp4.Mp4Atom:
        frag = representation.segments[seg_index]
        mp4_options = mp4.Options(
            mode='rw', lazy_load=True, bug_compatibility=options.bugCompatibility)
        if representation.encrypted:
            mp4_options.iv_size = representation.iv_size
        with current_media_file.open_file(start=frag.pos, buffer_size=16384) as reader:
            src = BufferedReader(
                reader, offset=frag.pos, size=frag.size, buffersize=16384)
            atom = mp4.Mp4Atom.load(src, options=mp4_options, use_wrapper=True)
            if parse_samples:
                atom.moof.traf.trun.parse_samples(
                    src, representation.nalLengthFieldLength)

        return atom

    def update_traf_if_required(self, options: OptionsContainer, traf: mp4.BoxWithChildren) -> bool:
        """
        Insert DRM specific data into the traf box, if required
        """
        modified = False
        for name, drm, __ in DrmContext.generate_drm_location_tuples(options):
            modif = drm.update_traf_if_required(getattr(options, name), traf)
            modified = modified or modif
        return modified

    def check_for_synthetic_http_error(
            self, content_type: str, seg_num: int,
            options: OptionsContainer) -> flask.Response | None:
        if content_type == 'audio':
            errs = options.audioErrors
        elif content_type == 'video':
            errs = options.videoErrors
        else:
            errs = options.textErrors
        for item in errs:
            code, pos = item
            if pos != seg_num:
                continue
            if (
                    code >= 500 and
                    options.failureCount is not None and
                    self.increment_error_counter(content_type, code) > options.failureCount
            ):
                self.reset_error_counter(content_type, code)
                continue
            return flask.make_response(f'Synthetic {code} for {content_type}', code)
        return None

    def apply_video_corruption(self, representation, segment_num, atom, dest, options):
        if options.videoCorruptionFrameCount is None:
            corrupt_frames = 4
        else:
            corrupt_frames = options.videoCorruptionFrameCount
        try:
            segments = [int(d, 10) for d in options.videoCorruption]
        except ValueError as err:
            logging.warning(f'Invalid options.videoCorruption value: {err}')
            return
        if segment_num not in segments:
            return
        for sample in atom.moof.traf.trun.samples:
            if corrupt_frames <= 0:
                return
            for nal in sample.nals:
                if nal.is_ref_frame and not nal.is_idr_frame:
                    junk = b'junk'
                    # put junk data in the last 20% of the NAL
                    junk_count = nal.size // (5 * len(junk))
                    if junk_count:
                        junk_size = len(junk) * junk_count
                        offset = nal.position + nal.size - junk_size
                        dest.seek(offset)
                        dest.write(junk_count * junk)
                    corrupt_frames -= 1
                    if corrupt_frames <= 0:
                        return
