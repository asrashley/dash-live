import os
import sys

class Box(object):
    def __init__(self, pos, size, duration=None):
        self.pos = pos
        self.size = size
        self.duration = duration

    def toJSON(self, pure=False):
        rv = {
            "pos": self.pos,
            "size": self.size,
        }
        if self.duration:
            rv["duration"] = self.duration
        return rv

    def __repr__(self):
        if self.duration:
            return '({:d},{:d},{:d})'.format(self.pos, self.size, self.duration)
        return '({:d},{:d})'.format(self.pos, self.size)


class Representation(object):
    VERSION = 2

    def __init__(self, id, **kwargs):
        def convert_dict(item):
            if isinstance(item, dict):
                item = Box(**item)
            elif isinstance(item, tuple):
                item = Box(*item)
            return item

        self.version = 0
        self.id = id
        self.segments = []
        self.startWithSAP = 1
        self.encrypted = False
        self.codecs = ''
        for key, value in kwargs.iteritems():
            object.__setattr__(self, key, value)
        self.segments = [convert_dict(s) for s in self.segments]
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

    def toJSON(self, pure=False):
        rv = {}
        for key, value in self.__dict__.iteritems():
            if key == 'num_segments':
                continue
            elif key == 'segments':
                rv[key] = map(lambda s: s.toJSON(pure=pure), self.segments)
            else:
                rv[key] = value
        return rv

    @classmethod
    def create(clz, filename, atoms, verbose=0):
        base_media_decode_time = None
        default_sample_duration = 0
        moov = None
        rv = Representation(id=os.path.splitext(filename.lower())[0],
                            filename=filename,
                            version=Representation.VERSION)
        for atom in atoms:
            seg = Box(pos=atom.position, size=atom.size)
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
                    for key in atom.pssh.key_ids:
                        rv.kids.add(key.encode('hex'))
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
                        rv.frameRate = rv.timescale / default_sample_duration
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
                        rv.kids = set([rv.default_kid])
                    if atom.trak.mdia.hdlr.handler_type == 'vide':
                        rv.contentType = "video"
                        if default_sample_duration > 0:
                            rv.frameRate = rv.timescale / default_sample_duration
                        rv.width = int(atom.trak.tkhd.width)
                        rv.height = int(atom.trak.tkhd.height)
                        try:
                            rv.width = avc.width
                            rv.height = avc.height
                        except AttributeError:
                            pass
                        # TODO: work out scan type
                        rv.scanType = "progressive"
                        # TODO: work out sample aspect ratio
                        rv.sar = "1:1"
                        if avc_type is not None:
                            rv.codecs = '%s.%02x%02x%02x' % (
                                avc_type,
                                avc.avcC.AVCProfileIndication,
                                avc.avcC.profile_compatibility,
                                avc.avcC.AVCLevelIndication)
                            rv.nalLengthFieldFength = avc.avcC.lengthSizeMinusOne + 1
                    elif atom.trak.mdia.hdlr.handler_type == 'soun':
                        rv.contentType = "audio"
                        rv.codecs = avc_type
                        if avc_type == "mp4a":
                            dsi = avc.esds.descriptor("DecoderSpecificInfo")
                            rv.sampleRate = dsi.sampling_frequency
                            rv.numChannels = dsi.channel_configuration
                            rv.codecs = "%s.%02x.%x" % (
                                avc_type, dsi.object_type,
                                dsi.audio_object_type)
                            if rv.numChannels == 7:
                                # 7 is a special case that means 7.1
                                rv.numChannels = 8
                        elif avc_type == "ec-3":
                            try:
                                rv.sampleRate = avc.sampling_frequency
                                rv.numChannels = 0
                                for s in avc.dec3.substreams:
                                    rv.numChannels += s.channel_count
                                    if s.lfeon:
                                        rv.numChannels += 1
                            except AttributeError:
                                pass
        if rv.encrypted:
            rv.kids = list(rv.kids)
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


if __name__ == '__main__':
    import io
    import mp4
    import utils

    src = utils.BufferedReader(io.FileIO(sys.argv[1], 'rb'))
    wrap = mp4.Wrapper(atom_type='wrap', parent=None,
                       children=mp4.Mp4Atom.create(src))
    rep = Representation.create(filename=sys.argv[1], atoms=wrap.children)
    print repr(rep)
