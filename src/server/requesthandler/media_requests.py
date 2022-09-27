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

from google.appengine.ext import blobstore

from mpeg import mp4
from server import models
from server.events import EventFactory
from .base import RequestHandlerBase
from utils.date_time import UTC, scale_timedelta
from utils.buffered_reader import BufferedReader

# blobstore_handlers.BlobstoreDownloadHandler):
class OnDemandMedia(RequestHandlerBase):
    """Handler that returns media fragments for the on-demand profile"""

    def get(self, filename, ext):
        name = filename + '.mp4'
        name = name.lower()
        mf = models.MediaFile.query(models.MediaFile.name == name).get()
        if mf is None:
            self.response.write('%s not found' % (name))
            self.response.set_status(404)
            return
        if ext == 'm4a':
            self.response.content_type = 'audio/mp4'
        elif ext == 'm4v':
            self.response.content_type = 'video/mp4'
        else:
            self.response.content_type = 'application/mp4'
        blob_info = blobstore.BlobInfo.get(mf.blob)
        try:
            start, end = self.get_http_range(blob_info.size)
        except ValueError as ve:
            self.response.write(str(ve))
            return
        if start is None:
            self.response.write('HTTP range must be specified')
            self.response.set_status(400)
            return
        blob_reader = blobstore.BlobReader(
            mf.blob, position=start, buffer_size=1 + end - start)
        data = blob_reader.read(1 + end - start)
        self.response.headers.add_header('Accept-Ranges', 'bytes')
        self.response.write(data)


# blobstore_handlers.BlobstoreDownloadHandler):
class LiveMedia(RequestHandlerBase):
    """Handler that returns media fragments"""

    def get(self, mode, filename, segment_num, ext):
        name = filename.lower() + '.mp4'
        mf = models.MediaFile.query(models.MediaFile.name == name).get()
        if mf is None:
            self.response.write('%s not found' % filename)
            self.response.set_status(404)
            return
        stream_name = filename.split('_')[0]
        stream = models.Stream.query(models.Stream.prefix == stream_name).get()
        if stream is None:
            self.response.write('%s not found' % stream_name)
            self.response.set_status(404)
            return
        representation = mf.representation
        try:
            audio, video = self.calculate_audio_video_context(
                stream, mode, representation.encrypted)
            # dash = self.calculate_dash_params(mode=mode, stream=stream)
        except ValueError as e:
            self.response.write('Invalid CGI parameters: %s' % (str(e)))
            self.response.set_status(400)
            return
        # TODO: add subtitle support
        if ext == 'm4a':
            adp_set = audio
        else:
            adp_set = video
        if video.representations:
            ref_representation = video.representations[0]
        else:
            ref_representation = audio.representations[0]
        if segment_num == 'init':
            mod_segment = segment_num = 0
        else:
            try:
                segment_num = int(segment_num, 10)
            except ValueError:
                segment_num = -1
            for code in self.INJECTED_ERROR_CODES:
                if self.request.params.get('%03d' % code) is not None:
                    try:
                        num_failures = int(
                            self.request.params.get('failures', '1'), 10)
                        for d in self.request.params.get(
                                '%03d' % code).split(','):
                            if int(d, 10) == segment_num:
                                # Only fail 5xx errors "num_failures" times
                                if code < 500 or self.increment_memcache_counter(
                                        segment_num, code) <= num_failures:
                                    self.response.write(
                                        'Synthetic %d for segment %d' % (code, segment_num))
                                    self.response.set_status(code)
                                    return
                    except ValueError as e:
                        self.response.write('Invalid CGI parameter %s: %s' % (
                            self.request.params.get(str(code)), str(e)))
                        self.response.set_status(400)
                        return
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
                _, elapsedTime, timeShiftBufferDepth = self.calculate_availability_start(
                    mode, now)
                lastFragment = adp_set.startNumber + int(scale_timedelta(
                    elapsedTime, representation.timescale, representation.segment_duration))
                firstFragment = (
                    lastFragment -
                    int(representation.timescale *
                        timeShiftBufferDepth / representation.segment_duration) - 1)
                firstFragment = max(adp_set.startNumber, firstFragment)
            else:
                firstFragment = adp_set.startNumber
                lastFragment = firstFragment + representation.num_segments - 1
            if segment_num < firstFragment or segment_num > lastFragment:
                self.response.write('Segment %d not found (valid range= %d->%d)' %
                                    (segment_num, firstFragment, lastFragment))
                self.response.set_status(404)
                return
            if mode == 'live':
                # elapsed_time is the time (in seconds) since availabilityStartTime
                # for the requested fragment
                elapsed_time = (
                    (segment_num - adp_set.startNumber) * ref_representation.segment_duration /
                    float(ref_representation.timescale))
                try:
                    mod_segment, origin_time = self.calculate_segment_from_timecode(
                        elapsed_time,
                        representation,
                        ref_representation)
                except ValueError:
                    raise
                    self.response.write('Segment %d not found (valid range= %d->%d)' %
                                        (segment_num, firstFragment, lastFragment))
                    self.response.set_status(404)
                    return
            else:
                mod_segment = 1 + segment_num - adp_set.startNumber
        self.response.content_type = adp_set.mimeType
        assert mod_segment >= 0 and mod_segment <= representation.num_segments
        frag = representation.segments[mod_segment]
        blob_reader = blobstore.BlobReader(
            mf.blob, position=frag.pos, buffer_size=16384)
        src = BufferedReader(
            blob_reader, offset=frag.pos, size=frag.size, buffersize=16384)
        options = mp4.Options(cache_encoded=True)
        if representation.encrypted:
            options.iv_size = representation.iv_size
        atom = mp4.Wrapper(
            atom_type='wrap', children=mp4.Mp4Atom.load(src, options=options))
        if self.request.params.get('corrupt') is not None:
            atom.moof.traf.trun.parse_samples(
                src, representation.nalLengthFieldFength)
        if segment_num == 0 and representation.encrypted:
            keys = models.Key.get_kids(representation.kids)
            drms = self.generate_drm_dict(stream)
            for drm in drms.values():
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
                delta = long(origin_time * representation.timescale)
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
        if segment_num > 0 and self.response.content_type == 'video/mp4':
            event_generators = EventFactory.create_event_generators(self.request)
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
        self.add_allowed_origins()
        data = io.BytesIO()
        atom.encode(data)
        if self.request.params.get('corrupt') is not None:
            try:
                self.apply_corruption(representation, segment_num, atom, data)
            except ValueError as e:
                self.response.write('Invalid CGI parameter %s: %s' % (
                    self.request.params.get('corrupt'), str(e)))
                self.response.set_status(400)
                return
        data = data.getvalue()[8:]  # [8:] is to skip the fake "wrap" box
        try:
            start, end = self.get_http_range(frag.size)
            if start is not None:
                data = data[start:end + 1]
        except (ValueError) as ve:
            self.response.write(str(ve))
            self.response.set_status(400)
            return
        self.response.headers.add_header('Accept-Ranges', 'bytes')
        self.response.out.write(data)

    def apply_corruption(self, representation, segment_num, atom, dest):
        try:
            corrupt_frames = int(self.request.params.get('frames', '4'), 10)
        except ValueError:
            corrupt_frames = 4
        for d in self.request.params.get('corrupt').split(','):
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
                        junk = 'junk'
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
