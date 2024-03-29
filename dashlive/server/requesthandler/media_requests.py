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

class OnDemandMedia(RequestHandlerBase):
    """
    Handler that returns media fragments for the on-demand profile.
    This handler does not support adding PSSH boxes into the init segment.
    """

    decorators = [uses_stream, uses_media_file]

    def get(self, stream, filename, ext):
        try:
            start, end, status, headers = self.get_http_range(current_media_file.blob.size)
        except ValueError as ve:
            logging.warning('Invalid HTTP range: %s', ve)
            return flask.make_response(f'Invalid HTTP range "{ve}"', 400)
        if start is None:
            logging.warning('HTTP range not specified')
            return flask.make_response('HTTP range must be specified', 400)
        if ext == 'm4a':
            headers['Content-Type'] = 'audio/mp4'
        elif ext == 'm4v':
            headers['Content-Type'] = 'video/mp4'
        else:
            headers['Content-Type'] = 'applicable/mp4'
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
        logging.debug(
            'LiveMedia.get: %s.%s stream=%s num=%s time=%s',
            filename, ext, stream, segment_num, segment_time)
        representation = current_media_file.representation
        try:
            options = self.calculate_options(mode, flask.request.args, current_stream)
        except ValueError as err:
            logging.error('Invalid CGI parameters: %s', err)
            return flask.make_response(f'Invalid CGI parameters: {err}', 400)
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
        if mf.content_type == 'audio':
            adp_id = 2
        elif mf.content_type == 'video':
            adp_id = 1
        elif mf.content_type == 'text':
            adp_id = 888
        else:
            return flask.make_response(
                f'Unsupported content_type {mf.content_type}', 404)
        adp_set = AdaptationSet(
            mode=options.mode, content_type=mf.content_type, id=adp_id,
            segment_timeline=options.segmentTimeline)
        adp_set.representations.append(current_media_file.representation)
        adp_set.compute_av_values()
        if segment_num == 'init':
            mod_segment = segment_num = 0
        else:
            try:
                if segment_num is not None:
                    segment_num = int(segment_num, 10)
            except ValueError as err:
                logging.warning('Invalid segment number: %s', err)
                return flask.make_response(f'Segment not found: {err}', 404)
            err = self.check_for_synthetic_http_error(mf.content_type, segment_num, options)
            if err:
                return err
            now = datetime.datetime.now(tz=UTC())
            timing = DashTiming(now, current_stream.timing_reference, options)
            adp_set.set_dash_timing(timing)
            try:
                first_fragment, last_fragment = representation.calculate_first_and_last_segment_number()
                logging.debug('elapsedTime=%s firstFragment=%d lastFragment=%d',
                              timing.elapsedTime, first_fragment, last_fragment)
                segment_num, mod_segment, origin_time = representation.calculate_segment_number_and_time(
                    segment_time, segment_num)
                logging.debug('segment=%d mod=%d origin=%d', segment_num, mod_segment, origin_time)
            except ValueError as err:
                logging.warning('ValueError: %s', err)
                msg = (f'Segment {segment_num} not found ' +
                       f'(valid range= {first_fragment} -> ' +
                       f'{last_fragment}): {err}')
                logging.info("%s", msg)
                return flask.make_response(msg, 404)
            if segment_num < first_fragment or segment_num > last_fragment:
                logging.info(
                    '%s: Request for fragment %d that is not available (%d -> %d)',
                    now, segment_num, first_fragment, last_fragment)
                if mode == 'live':
                    first_tc = timing.availabilityStartTime + datetime.timedelta(
                        seconds=(first_fragment * representation.segment_duration /
                                 representation.timescale))
                    logging.debug('oldest fragment %d start = %s', first_fragment, first_tc)
                return flask.make_response(
                    f'Segment {segment_num} not found (valid range= {first_fragment}->{last_fragment})',
                    404)
        assert mod_segment >= 0 and mod_segment <= representation.num_media_segments
        frag = representation.segments[mod_segment]
        mp4_options = mp4.Options(
            mode='rw', lazy_load=True, bug_compatibility=options.bugCompatibility)
        if representation.encrypted:
            mp4_options.iv_size = representation.iv_size
        with current_media_file.open_file(start=frag.pos, buffer_size=16384) as reader:
            src = BufferedReader(
                reader, offset=frag.pos, size=frag.size, buffersize=16384)
            atom = mp4.Mp4Atom.load(src, options=mp4_options, use_wrapper=True)
        if adp_set.content_type == 'video' and options.videoCorruption:
            atom.moof.traf.trun.parse_samples(
                src, representation.nalLengthFieldLength)
        if segment_num == 0 and representation.encrypted:
            keys = models.Key.get_kids(representation.kids)
            drms = self.generate_drm_dict(stream, keys, options)
            for drm in list(drms.values()):
                if 'moov' in drm:
                    pssh = drm["moov"](representation, keys)
                    atom.moov.append_child(pssh)
        if mode == 'live':
            if segment_num == 0:
                try:
                    # remove the mehd box as this stream is not supposed to
                    # have a fixed duration
                    del atom.moov.mehd
                except AttributeError:
                    pass
            else:
                atom.moof.traf.tfdt.base_media_decode_time += origin_time

                # Update the sequenceNumber field in the MovieFragmentHeader
                # box
                atom.moof.mfhd.sequence_number = segment_num
                diff = None
                if segment_time is not None:
                    diff = segment_time - atom.moof.traf.tfdt.base_media_decode_time
                logging.debug(
                    r'%s: $Time$ want=%s got=%d (%s)',
                    filename, segment_time, atom.moof.traf.tfdt.base_media_decode_time, diff)
                diff = None
                if segment_num is not None:
                    diff = segment_num - atom.moof.mfhd.sequence_number
                logging.debug(
                    r'%s: $Number$ want=%s got=%d (%s)',
                    filename, segment_num, atom.moof.mfhd.sequence_number, diff)
                logging.debug(
                    r'%s: origin=%d duration=%d',
                    filename, origin_time, representation.segment_duration)
            try:
                # remove any sidx box as it has a baseMediaDecodeTime and it's
                # an optional index
                del atom.sidx
            except AttributeError:
                pass
        moof_modified = False
        traf_modified = False
        if segment_num > 0 and adp_set.content_type == 'video':
            event_generators = EventFactory.create_event_generators(options)
            if event_generators:
                logging.debug('creating emsg boxes')
                moof_idx = atom.index('moof')
                for evgen in event_generators:
                    boxes = evgen.create_emsg_boxes(
                        moof=atom.moof,
                        adaptation_set=adp_set,
                        segment_num=segment_num,
                        mod_segment=mod_segment,
                        representation=representation)
                    # the emsg boxes must be inserted before the
                    # moof box (see DASH section 5.10.3.3)
                    for idx, emsg in enumerate(boxes):
                        atom.children.insert(moof_idx + idx, emsg)
                        moof_modified = True
        if representation.encrypted and segment_num > 0:
            traf_modified = self.update_traf_if_required(options, atom.moof.traf)
            moof_modified = moof_modified or traf_modified
        if moof_modified:
            tfhd = atom.moof.traf.find_child('tfhd')
            if tfhd is not None:
                # force base_data_offset to be re-calculated when the
                # tfhd box is encoded
                tfhd.base_data_offset = None
        if traf_modified:
            saio = atom.moof.traf.find_child('saio')
            senc = atom.moof.traf.find_child('senc')
            if saio is not None and senc is not None:
                # force re-calculation of SAIO offset to SENC box
                saio.offsets = None
        dest = io.BytesIO()
        atom.encode(dest)
        if mf.content_type == 'video' and options.videoCorruption:
            self.apply_video_corruption(representation, segment_num, atom, dest, options)
        data = dest.getvalue()
        headers = {
            'Accept-Ranges': 'bytes',
            'Content-Type': adp_set.mimeType,
        }
        status = 200
        try:
            start, end, status, range_headers = self.get_http_range(len(data))
            if start is not None:
                data = data[start:end + 1]
            headers.update(range_headers)
        except (ValueError) as ve:
            return flask.make_response(f'{ve}', 400)
        self.add_allowed_origins(headers)
        return flask.make_response((data, status, headers))

    def update_traf_if_required(self, options: OptionsContainer, traf: mp4.BoxWithChildren) -> bool:
        """
        Insert DRM specific data into the traf box, if required
        """
        modified = False
        for name, drm, __ in self.generate_drm_location_tuples(options):
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
