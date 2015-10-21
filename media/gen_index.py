import argparse, datetime, fnmatch, io, re, os, struct, sys

sys.path.append(os.path.join(os.path.dirname(__file__),'..'))

import mp4, nal, utils
from segment import Representation, Segment

def create_representation(filename, args):
    print filename
    stats = os.stat(filename)
    parser = mp4.IsoParser()
    atoms = parser.walk_atoms(filename)
    repr = Representation(id=os.path.splitext(filename.upper())[0],
                          filename=filename.replace('\\','/'))
    base_media_decode_time=None
    default_sample_duration=None
    moov = None
    for atom in atoms:
        if atom.type=='ftyp':
            if args.debug:
                print('Init seg',atom)
            else:
                sys.stdout.write('I')
                sys.stdout.flush()
            seg = Segment(seg=atom)
            repr.segments.append(seg)
        elif atom.type=='moof':
            if args.debug:
                print 'Fragment %d '%(len(repr.segments)+1)
            else:
                sys.stdout.write('f')
                sys.stdout.flush()
            seg = Segment(seg=atom, tfdt=atom.traf.tfdt, mfhd=atom.mfhd)
            dur=0
            for sample in atom.traf.trun.samples:
                if sample.duration is None:
                    sample.duration=moov.mvex.trex.default_sample_duration
                dur += sample.duration
            seg.seg.duration = dur
            base_media_decode_time = atom.traf.tfdt.base_media_decode_time
            repr.segments.append(seg)
            if default_sample_duration is None:
                default_sample_duration = 0
                for sample in atom.traf.trun.samples:
                    default_sample_duration += sample.duration
                default_sample_duration = default_sample_duration // len(atom.traf.trun.samples)
                print('Average sample duration %d'%default_sample_duration)
                if repr.contentType=="video" and default_sample_duration:
                    repr.frameRate = repr.timescale / default_sample_duration
            if args.debug:
                trun = atom.traf.trun
                print trun
                src = open(filename,'rb')
                try:
                    trun.parse_samples(src,4)
                    for sample in atom.traf.trun.samples:
                        for nal in sample.nals:
                            print(nal)
                finally:
                    src.close()
        elif atom.type in ['sidx','moov','mdat','free'] and repr.segments:
            if args.debug:
                print('Extend fragment %d with %s'%(len(repr.segments), atom.type))
            seg = repr.segments[-1]
            seg.seg.size = atom.position - seg.seg.pos + atom.size
            if atom.type=='moov':
                if not args.debug:
                    sys.stdout.write('M')
                    sys.stdout.flush()
                moov = atom
                repr.timescale = atom.trak.mdia.mdhd.timescale
                repr.language =  atom.trak.mdia.mdhd.language
                try:
                    default_sample_duration = atom.mvex.trex.default_sample_duration
                except AttributeError:
                    print('Warning: Unable to find default_sample_duration')
                    default_sample_duration = None
                if atom.trak.mdia.hdlr.handler_type=='vide':
                    repr.contentType="video"
                    if default_sample_duration is not None:
                        repr.frameRate = repr.timescale / default_sample_duration
                    repr.width = int(atom.trak.tkhd.width)
                    repr.height = int(atom.trak.tkhd.height)
                    #TODO: work out scan type
                    repr.scanType="progressive"
                    #TODO: work out sample aspect ratio
                    repr.sar="1:1"
                    avc=None
                    try:
                        avc = atom.trak.mdia.minf.stbl.stsd.avc3
                    except AttributeError:
                        pass
                    if avc is None:
                        try:
                            avc = atom.trak.mdia.minf.stbl.stsd.avc1
                        except AttributeError:
                            pass
                    if avc is None:
                        try:
                            avc = atom.trak.mdia.minf.stbl.stsd.encv
                        except AttributeError:
                            pass
                    if avc is None:
                        try:
                            avc = atom.trak.mdia.minf.stbl.stsd.enca
                        except AttributeError:
                            pass
                    if avc is not None:
                        avc_type = avc.type
                        if avc_type=='encv' or avc_type=='enca':
                            avc_type = avc.sinf.frma.data_format
                            repr.encrypted=True
                        repr.codecs = '%s.%02x%02x%02x'%(avc_type,
                                                         avc.avcC.AVCProfileIndication,
                                                         avc.avcC.profile_compatibility,
                                                         avc.avcC.AVCLevelIndication)
                elif atom.trak.mdia.hdlr.handler_type=='soun':
                    repr.contentType="audio"
                    try:
                        avc = atom.trak.mdia.minf.stbl.stsd.mp4a
                        dsi = avc.esds.DecoderSpecificInfo
                        repr.sampleRate = dsi.sampling_frequency
                        repr.numChannels = dsi.channel_configuration
                        repr.codecs = "%s.%02x.%02x"%(avc.type, avc.esds.DecoderSpecificInfo.object_type, dsi.audio_object_type)
                        if repr.numChannels==7:
                            # 7 is a special case that means 7.1
                            repr.numChannels=8
                    except AttributeError:
                        avc = atom.trak.mdia.minf.stbl.stsd.ec_3
                        repr.sampleRate = avc.sampling_frequency
                        repr.numChannels = avc.channel_count
                        if avc.dec3.substreams:
                            repr.numChannels = 0
                            for s in avc.dec3.substreams:
                                repr.numChannels += s.channel_count
                                if s.lfeon:
                                    repr.numChannels += 1
                        repr.codecs = avc.type
                try:
                    seg.add(mehd=atom.mvex.mehd)
                except AttributeError:
                    pass
            elif atom.type=='sidx':
                seg.add(sidx=atom)
    sys.stdout.write('\r\n')
    if len(repr.segments)>2:
        seg_dur = base_media_decode_time/(len(repr.segments)-2)
        repr.media_duration = 0
        for seg in repr.segments[1:]:
            repr.media_duration += seg.seg.duration
        repr.max_bitrate = 8 * repr.timescale * max([seg.seg.size for seg in repr.segments]) / seg_dur
        repr.segment_duration = seg_dur
        repr.bitrate = int(8 * repr.timescale * stats.st_size/repr.media_duration + 0.5)
    return repr

def create_index_file(filename, args):
    repr = create_representation(filename, args)
    if args.codec:
        codec_src = create_representation(args.codec[0], args)
        repr.codecs = codec_src.codecs
        if repr.contentType=='video':
            repr.height = codec_src.height
            repr.width = codec_src.width
            try:
                repr.frameRate = codec_src.frameRate
            except AttributeError:
                pass
        else:
            repr.sampleRate = codec_src.sampleRate
            repr.numChannels = codec_src.numChannels
    if args.manifest:
        print('Creating manifest '+args.manifest[0])
        dest = open(args.manifest[0], 'wb')
        dest.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        dest.write('<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" ')
        dest.write('mediaPresentationDuration="%s" minBufferTime="PT10S" '%utils.toIsoDuration(repr.media_duration/repr.timescale))
        dest.write('profiles="urn:mpeg:dash:profile:isoff-on-demand:2011" type="static" ')
        dest.write('xsi:schemaLocation="urn:mpeg:dash:schema:mpd:2011 http://standards.iso.org/ittf/PubliclyAvailableStandards/MPEG-DASH_schema_files/DASH-MPD.xsd">\n')
        dest.write(' <Period start="PT0S" duration="%s">\n'%utils.toIsoDuration(repr.media_duration/repr.timescale))
        if repr.contentType=='audio':
            ext = 'm4a'
            mimeType='audio/mp4'
        else:
            ext = 'm4v'
            mimeType='video/mp4'
        dest.write('  <AdaptationSet contentType="%s" group="1" lang="%s" mimeType="%s" segmentAlignment="true" subsegmentAlignment="true" subsegmentStartsWithSAP="1">\n'%(repr.contentType,repr.language,mimeType))
        try:
            dest.write('   <Representation audioSamplingRate="%d" bandwidth="%d" codecs="%s" id="%s">\n'%(repr.sampleRate, repr.bitrate, repr.codecs, repr.id))
        except AttributeError:
            dest.write('   <Representation frameRate="%d" bandwidth="%d" codecs="%s" id="%s" height="%d" width="%d">\n'%(repr.frameRate, repr.bitrate, repr.codecs, repr.id, repr.height, repr.width))
        if args.split:
            dest.write('     <SegmentTemplate presentationTimeOffset="0" timescale="%d" startNumber="1" '%(repr.timescale))
            dest.write('initialization="$RepresentationID$/init.%s" media="$RepresentationID$/$Number%%05d$.%s" '%(ext,ext))
            dest.write('duration="%d"/>\n'%(repr.segment_duration))
        else:
            dest.write('     <BaseURL>%s</BaseURL>\n'%filename)
            dest.write('     <SegmentList duration="%d" timescale="%d">\n'%(repr.segment_duration, repr.timescale))
            dest.write('       <Initialization range="%d-%d"/>\n'%(repr.segments[0].seg.pos,repr.segments[0].seg.pos+repr.segments[0].seg.size-1))
            for seg in repr.segments[1:]:
                dest.write('       <SegmentURL d="%d" mediaRange="%d-%d"/>\n'%(seg.seg.duration, seg.seg.pos, seg.seg.pos+seg.seg.size-1))
            dest.write('     </SegmentList>\n')
        dest.write('   </Representation>\n')
        dest.write('  </AdaptationSet>\n')
        dest.write(' </Period>\n')
        dest.write('</MPD>\n')
        dest.close()
    if args.split:
        ext = 'm4a' if repr.contentType=='audio' else 'm4v'
        src_file = io.FileIO(filename, 'rb')
        for idx,seg in enumerate(repr.segments):
            if idx==0:
                dst_filename = os.path.join(args.split[0],'init.%s'%ext)
            else:
                dst_filename = os.path.join(args.split[0], '%05d.%s'%(idx,ext))
            print dst_filename
            dst_file = io.FileIO(dst_filename,'wb')
            src_file.seek(seg.seg.pos)
            data = src_file.read(seg.seg.size)
            dst_file.write(data)
            dst_file.close()
        src_file.close()
    if args.index:
        print('Creating '+repr.id+'.py')
        dest = open(repr.id+'.py', 'wb')
        dest.write('from segment import Representation\n')
        dest.write('representation=')
        dest.write(str(repr))
        dest.write('\r\n')
        dest.close()

parser = argparse.ArgumentParser(description='MP4 parser and index generation')
parser.add_argument('-d', '--debug', action="store_true")
parser.add_argument('-c', '--codec', help='MP4 file that contains codec information', nargs=1, metavar=('mp4file'))
parser.add_argument('-i', '--index', help='Generate a python index file', action="store_true")
parser.add_argument('-m', '--manifest', help='Generate a manifest file', nargs=1, metavar=('mpdfile'))
parser.add_argument('-s', '--split', help='Split MP4 file into fragments', nargs=1, metavar=('mp4file'))
parser.add_argument('mp4file', help='Filename of MP4 file', nargs='+', default=None)
args = parser.parse_args()

for fname in args.mp4file:
    if '*' in fname or '?' in fname:
        directory = os.path.dirname(fname)
        if directory=='':
            directory='.'
        files = os.listdir(directory)
        for filename in fnmatch.filter(files, fname):
            create_index_file(filename, args)
    else:
        create_index_file(fname, args)
