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

import os
import sys

from drm.keymaterial import KeyMaterial
from utils.list_of import ListOf
from utils.object_with_fields import ObjectWithFields

from .segment import Segment

class Representation(ObjectWithFields):
    OBJECT_FIELDS = {
        'segments': ListOf(Segment),
        'kids': ListOf(KeyMaterial),
    }
    DEFAULT_VALUES = {
        'bitrate': None,
        'contentType': None,
        'codecs': None,
        'default_kid': None,
        'iv_size': None,
        'encrypted': False,
        'mediaDuration': None,
        'max_bitrate': None,
        'nalLengthFieldLength': None,
        'segment_duration': None,
        'startWithSAP': 1,
        'timescale': 1,
        'track_id': 1,
        'version': 0,
    }
    #REQUIRED_FIELDS = {
    #    'id': str,
    #}
    VERSION = 2

    def __init__(self, **kwargs):
        super(Representation, self).__init__(**kwargs)
        defaults = {
            'language': 'und',
            'kids': [],
            'segments': [],
            'codecs': '',
        }
        if self.contentType == 'video':
            defaults.update({
                'frameRate': None,
                'height': None,
                'scanType': "progressive",
                'sar': "1:1",
                'width': None,
            })
        elif self.contentType == 'audio':
            defaults.update({
                'sampleRate': 48000,
                'numChannels': 1,
            })
        self.apply_defaults(defaults)
        self.num_segments = len(self.segments) - 1

    def __repr__(self):
        args = []
        for key, value in self.__dict__.iteritems():
            if key == 'num_segments':
                continue
            if isinstance(value, str):
                value = '"%s"' % value
            else:
                value = str(value)
            args.append('%s=%s' % (key, value))
        args = ','.join(args)
        return 'Representation(' + args + ')'

    @classmethod
    def load(clz, filename, atoms, verbose=0):
        base_media_decode_time = None
        default_sample_duration = 0
        moov = None
        rv = Representation(id=os.path.splitext(filename.lower())[0],
                            filename=filename,
                            version=Representation.VERSION)
        key_ids = set()
        for atom in atoms:
            seg = Segment(pos=atom.position, size=atom.size)
            if atom.atom_type == 'ftyp':
                if verbose > 1:
                    print('Init seg', atom)
                elif verbose > 0:
                    sys.stdout.write('I')
                    sys.stdout.flush()
                rv.segments.append(seg)
            elif atom.atom_type == 'moof':
                if verbose > 1:
                    print 'Fragment %d ' % (len(rv.segments) + 1)
                elif verbose > 0:
                    sys.stdout.write('f')
                    sys.stdout.flush()
                dur = 0
                for sample in atom.traf.trun.samples:
                    if not sample.duration:
                        sample.duration = moov.mvex.trex.default_sample_duration
                    dur += sample.duration
                seg.duration = dur
                try:
                    for kid in atom.pssh.key_ids:
                        key_ids.add(KeyMaterial(raw=kid))
                except AttributeError:
                    pass
                base_media_decode_time = atom.traf.tfdt.base_media_decode_time
                rv.segments.append(seg)
                if default_sample_duration == 0:
                    for sample in atom.traf.trun.samples:
                        default_sample_duration += sample.duration
                    default_sample_duration = default_sample_duration // len(atom.traf.trun.samples)
                    if verbose > 1:
                        print('Average sample duration %d' % default_sample_duration)
                    if rv.contentType == "video" and default_sample_duration:
                        rv.add_field('frameRate', rv.timescale / default_sample_duration)
            elif atom.atom_type in ['sidx', 'moov', 'mdat', 'free'] and rv.segments:
                if verbose > 1:
                    print('Extend fragment %d with %s' % (len(rv.segments), atom.atom_type))
                seg = rv.segments[-1]
                seg.size = atom.position - seg.pos + atom.size
                if atom.atom_type == 'moov':
                    if verbose == 1:
                        sys.stdout.write('M')
                        sys.stdout.flush()
                    moov = atom
                    rv.timescale = atom.trak.mdia.mdhd.timescale
                    rv.language = atom.trak.mdia.mdhd.language
                    rv.track_id = atom.trak.tkhd.track_id
                    try:
                        default_sample_duration = atom.mvex.trex.default_sample_duration
                    except AttributeError:
                        print('Warning: Unable to find default_sample_duration')
                        default_sample_duration = 0
                    avc = None
                    avc_type = None
                    for box in ['avc1', 'avc3', 'mp4a', 'ec_3', 'encv', 'enca']:
                        try:
                            avc = getattr(atom.trak.mdia.minf.stbl.stsd, box)
                            avc_type = avc.atom_type
                            break
                        except AttributeError:
                            pass
                    if avc_type == 'enca' or avc_type == 'encv':
                        avc_type = avc.sinf.frma.data_format
                        rv.encrypted = True
                        rv.default_kid = avc.sinf.schi.tenc.default_kid.encode('hex')
                        rv.iv_size = avc.sinf.schi.tenc.iv_size
                        key_ids.add(KeyMaterial(hex=rv.default_kid))
                    if atom.trak.mdia.hdlr.handler_type == 'vide':
                        rv.contentType = "video"
                        if default_sample_duration > 0:
                            rv.add_field('frameRate', rv.timescale / default_sample_duration)
                        rv.add_field('width', int(atom.trak.tkhd.width))
                        rv.add_field('height', int(atom.trak.tkhd.height))
                        try:
                            rv.width = avc.width
                            rv.height = avc.height
                        except AttributeError:
                            pass
                        # TODO: work out scan type
                        rv.add_field('scanType', "progressive")
                        # TODO: work out sample aspect ratio
                        rv.add_field('sar', "1:1")
                        if avc_type is not None:
                            rv.codecs = '%s.%02x%02x%02x' % (
                                avc_type,
                                avc.avcC.AVCProfileIndication,
                                avc.avcC.profile_compatibility,
                                avc.avcC.AVCLevelIndication)
                            rv.nalLengthFieldLength = avc.avcC.lengthSizeMinusOne + 1
                    elif atom.trak.mdia.hdlr.handler_type == 'soun':
                        rv.contentType = "audio"
                        rv.codecs = avc_type
                        if avc_type == "mp4a":
                            dsi = avc.esds.descriptor("DecoderSpecificInfo")
                            rv.add_field('sampleRate', dsi.sampling_frequency)
                            rv.add_field('numChannels', dsi.channel_configuration)
                            rv.codecs = "%s.%02x.%x" % (
                                avc_type, dsi.object_type,
                                dsi.audio_object_type)
                            if rv.numChannels == 7:
                                # 7 is a special case that means 7.1
                                rv.numChannels = 8
                        elif avc_type == "ec-3":
                            try:
                                rv.add_field('sampleRate', avc.sampling_frequency)
                                rv.add_field('numChannels', 0)
                                for s in avc.dec3.substreams:
                                    rv.numChannels += s.channel_count
                                    if s.lfeon:
                                        rv.numChannels += 1
                            except AttributeError:
                                pass
        if rv.encrypted:
            rv.kids = list(key_ids)
        if verbose == 1:
            sys.stdout.write('\r\n')
        if len(rv.segments) > 2:
            # We need to exclude the last fragment when trying to estimate fragment
            # duration, as the last one might be truncated. By using base_media_decode_time
            # of the last fragment and dividing by number of media fragments (minus one)
            # provides the best estimate of fragment duration.
            # Note: len(rv.segments) also includes the init segment, hence the need for -2
            seg_dur = base_media_decode_time / (len(rv.segments) - 2)
            rv.mediaDuration = 0
            for seg in rv.segments[1:]:
                rv.mediaDuration += seg.duration
            rv.max_bitrate = 8 * rv.timescale * max([seg.size for seg in rv.segments]) / seg_dur
            rv.segment_duration = seg_dur
            file_size = rv.segments[-1].pos + rv.segments[-1].size - rv.segments[0].pos
            rv.bitrate = int(8 * rv.timescale * file_size / rv.mediaDuration + 0.5)
        return rv

    def generateSegmentDurations(self):
        # TODO: support live profile
        def output_s_node(sn):
            if sn["duration"] is None:
                return
            c = ' r="{:d}"'.format(sn["count"] - 1) if sn["count"] > 1 else ''
            rv.append('<S {} d="{:d}"/>'.format(c, sn["duration"]))
        rv = ['<SegmentDurations timescale="%d">' % (self.timescale)]
        s_node = {
            "duration": None,
            "count": 0,
        }
        for seg in self.segments:
            try:
                if seg.duration != s_node["duration"]:
                    output_s_node(s_node)
                    s_node["count"] = 0
                s_node["duration"] = seg.duration
                s_node["count"] += 1
            except AttributeError:
                # init segment does not have a duration
                pass
        output_s_node(s_node)
        rv.append('</SegmentDurations>')
        return '\n'.join(rv)

    def generateSegmentList(self):
        # TODO: support live profile
        rv = ['<SegmentList timescale="%d" duration="%d">' %
              (self.timescale, self.mediaDuration)]
        first = True
        for seg in self.segments:
            if first:
                rv.append(
                    '<Initialization range="{start:d}-{end:d}"/>'.format(
                        start=seg.pos, end=seg.pos + seg.size - 1))
                first = False
            else:
                rv.append('<SegmentURL mediaRange="{start:d}-{end:d}"/>'.format(
                    start=seg.pos, end=seg.pos + seg.size - 1))
        rv.append('</SegmentList>')
        return '\n'.join(rv)

if __name__ == '__main__':
    import io
    import mp4
    import utils

    src = utils.BufferedReader(io.FileIO(sys.argv[1], 'rb'))
    wrap = mp4.Wrapper(atom_type='wrap', parent=None,
                       children=mp4.Mp4Atom.load(src))
    rep = Representation.load(filename=sys.argv[1], atoms=wrap.children)
    print repr(rep)
