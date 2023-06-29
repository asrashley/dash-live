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

from __future__ import division
from builtins import str
from past.utils import old_div
import datetime
import io
import logging

import flask

from dashlive.mpeg import mp4
from dashlive.server import models
from dashlive.server.events.factory import EventFactory
from dashlive.utils.date_time import UTC, scale_timedelta
from dashlive.utils.buffered_reader import BufferedReader

from .base import RequestHandlerBase
from .dash_timing import DashTiming
from .decorators import (
    uses_stream,
    uses_media_file,
    current_media_file,
    current_stream
)

# blobstore_handlers.BlobstoreDownloadHandler):
class OnDemandMedia(RequestHandlerBase):
    """Handler that returns media fragments for the on-demand profile"""

    decorators = [uses_stream, uses_media_file]

    def get(self, stream, filename, ext):
        try:
            start, end, status, headers = self.get_http_range(current_media_file.blob.size)
        except ValueError as ve:
            return flask.make_response(f'Invalid HTTP range "{ve}"', 400)
        if start is None:
            return flask.make_response.write('HTTP range must be specified', 400)
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
            segment_num: str, ext: str) -> flask.Response:
        logging.debug('LiveMedia.get: %s %s %s %s', stream, filename, segment_num, ext)
        representation = current_media_file.representation
        audio = None
        mf = current_media_file
        try:
            # TODO: add subtitle support
            if mf.content_type == 'audio':
                audio = self.calculate_audio_context(
                    current_stream, mode, representation.encrypted)
                assert audio.content_type == 'audio'
                video = self.calculate_video_context(
                    current_stream, mode, representation.encrypted, max_items=1)
                assert video.content_type == 'video'
                adp_set = audio
            else:
                video = self.calculate_video_context(
                    current_stream, mode, representation.encrypted)
                adp_set = video
        except ValueError as e:
            return flask.make_response(f'Invalid CGI parameters: {e}', 400)
        if video.representations:
            ref_representation = video.representations[0]
        else:
            ref_representation = audio.representations[0]
        adp_set.set_reference_representation(ref_representation)
        if segment_num == 'init':
            mod_segment = segment_num = 0
        else:
            try:
                segment_num = int(segment_num, 10)
            except ValueError as err:
                return flask.make_response(f'Segment not found: {err}', 404)
            for code in self.INJECTED_ERROR_CODES:
                err_segs = flask.request.args.get(f'{code:03d}', None)
                if err_segs is None:
                    continue
                try:
                    num_failures = int(
                        flask.request.args.get('failures', '1'), 10)
                except ValueError:
                    msg = 'Invalid value "{flask.request.args["failures"]}" for failures parameter'
                    return flask.make_response((msg, 400,))
                try:
                    for d in err_segs.split(','):
                        if int(d, 10) != segment_num:
                            continue
                        # Only fail 5xx errors "num_failures" times
                        if (code >= 500 and
                                self.increment_error_counter('media', code) > num_failures):
                            self.reset_error_counter('media', code)
                            continue
                        msg = f'Synthetic {code} for segment {segment_num}'
                        return flask.make_response((msg, code,))
                except ValueError as e:
                    msg = f'Invalid CGI parameter value for {code} "{err_segs}": {e}'
                    return flask.make_response((msg, 400,))
            if mode == 'live':
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
                now = datetime.datetime.now(tz=UTC())
                timing = DashTiming(mode, now, ref_representation, flask.request.args)
                adp_set.set_dash_timing(timing)
                lastFragment = adp_set.startNumber + int(scale_timedelta(
                    timing.elapsedTime, representation.timescale, representation.segment_duration))
                firstFragment = (
                    lastFragment -
                    int(old_div(representation.timescale *
                        timing.timeShiftBufferDepth, representation.segment_duration)) - 1)
                firstFragment = max(adp_set.startNumber, firstFragment)
                logging.debug('elapsedTime=%s firstFragment=%d lastFragment=%d',
                              timing.elapsedTime, firstFragment, lastFragment)
                try:
                    timecode = ((segment_num - adp_set.startNumber) *
                                ref_representation.segment_duration /
                                float(ref_representation.timescale))
                    mod_segment, origin_time = representation.calculate_segment_from_timecode(
                        timecode)
                except ValueError as err:
                    logging.warning('ValueError: %s', err)
                    self.response.write('Segment %d not found (valid range= %d->%d)' %
                                        (segment_num, firstFragment, lastFragment))
                    self.response.set_status(404)
                    return
            else:
                firstFragment = adp_set.startNumber
                lastFragment = firstFragment + representation.num_segments - 1
                mod_segment = 1 + segment_num - adp_set.startNumber
            if segment_num < firstFragment or segment_num > lastFragment:
                self.response.write('Segment %d not found (valid range= %d->%d)' %
                                    (segment_num, firstFragment, lastFragment))
                self.response.set_status(404)
                return
        assert mod_segment >= 0 and mod_segment <= representation.num_segments
        frag = representation.segments[mod_segment]
        options = mp4.Options(cache_encoded=True)
        if representation.encrypted:
            options.iv_size = representation.iv_size
        if flask.request.args.get('bugs', None) is not None:
            options.bug_compatibility = flask.request.args['bugs']
        with current_media_file.open_file(start=frag.pos, buffer_size=16384) as reader:
            src = BufferedReader(
                reader, offset=frag.pos, size=frag.size, buffersize=16384)
            atom = mp4.Wrapper(
                atom_type='wrap', children=mp4.Mp4Atom.load(src, options=options))
        if adp_set.content_type == 'video' and flask.request.args.get('corrupt') is not None:
            atom.moof.traf.trun.parse_samples(
                src, representation.nalLengthFieldLength)
        if segment_num == 0 and representation.encrypted:
            keys = models.Key.get_kids(representation.kids)
            drms = self.generate_drm_dict(stream, keys)
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
                # Update the baseMediaDecodeTime to take account of the number of times the
                # stream would have looped since availabilityStartTime
                delta = int(origin_time * representation.timescale)
                if delta < 0:
                    raise IOError("Failure in calculating delta %s %d %d %d" % (
                        str(delta), segment_num, mod_segment, adp_set.startNumber))
                atom.moof.traf.tfdt.base_media_decode_time += delta

                # Update the sequenceNumber field in the MovieFragmentHeader
                # box
                atom.moof.mfhd.sequence_number = segment_num
            try:
                # remove any sidx box as it has a baseMediaDecodeTime and it's
                # an optional index
                del atom.sidx
            except AttributeError:
                pass
        moof_modified = False
        traf_modified = False
        if segment_num > 0 and adp_set.content_type == 'video':
            event_generators = EventFactory.create_event_generators(flask.request)
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
            traf_modified = self.update_traf_if_required(atom.moof.traf)
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
        data = io.BytesIO()
        for child in atom.children:
            child.encode(data)
        if mf.content_type == 'video' and flask.request.args.get('corrupt') is not None:
            try:
                self.apply_video_corruption(representation, segment_num, atom, data)
            except ValueError as e:
                corrupt = flask.request.args.get('corrupt')
                return flask.make_response(
                    f'Invalid CGI parameter {corrupt}: {e}', 400)
        data = data.getvalue()
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

    def update_traf_if_required(self, traf):
        """
        Insert DRM specific data into the traf box, if required
        """
        modified = False
        for _, drm, __ in self.generate_drm_location_tuples():
            modif = drm.update_traf_if_required(flask.request.args, traf)
            modified = modified or modif
        return modified

    def apply_video_corruption(self, representation, segment_num, atom, dest):
        try:
            corrupt_frames = int(flask.request.args.get('frames', '4'), 10)
        except ValueError:
            corrupt_frames = 4
        for d in flask.request.args.get('corrupt').split(','):
            try:
                d = int(d, 10)
            except ValueError:
                continue
            if d != segment_num:
                continue
            for sample in atom.moof.traf.trun.samples:
                if corrupt_frames <= 0:
                    break
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
                                break
