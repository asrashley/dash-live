import argparse, datetime, fnmatch, io, re, os, struct, sys

sys.path.append(os.path.join(os.path.dirname(__file__),'..'))

import mp4, nal, utils
from segment import Representation

def create_representation(filename, args):
    print filename
    parser = mp4.IsoParser()
    atoms = parser.walk_atoms(filename)
    verbose = 2 if args.debug else 1
    return Representation.create(filename=filename.replace('\\','/'), atoms=atoms, verbose=verbose)

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
        dest.write('mediaPresentationDuration="%s" minBufferTime="PT10S" '%utils.toIsoDuration(repr.mediaDuration/repr.timescale))
        dest.write('profiles="urn:mpeg:dash:profile:isoff-on-demand:2011" type="static" ')
        dest.write('xsi:schemaLocation="urn:mpeg:dash:schema:mpd:2011 http://standards.iso.org/ittf/PubliclyAvailableStandards/MPEG-DASH_schema_files/DASH-MPD.xsd">\n')
        dest.write(' <Period start="PT0S" duration="%s">\n'%utils.toIsoDuration(repr.mediaDuration/repr.timescale))
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
            dest.write('       <Initialization range="%d-%d"/>\n'%(repr.segments[0].pos,repr.segments[0].pos+repr.segments[0].size-1))
            for seg in repr.segments[1:]:
                dest.write('       <SegmentURL d="%d" mediaRange="%d-%d"/>\n'%(seg.duration, seg.pos, seg.pos+seg.size-1))
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
            src_file.seek(seg.pos)
            data = src_file.read(seg.size)
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MP4 parser and index generation')
    parser.add_argument('-d', '--debug', action="store_true")
    parser.add_argument('-c', '--codec', help='MP4 file that contains codec information', nargs=1,
                        metavar=('mp4file'))
    parser.add_argument('-i', '--index', help='Generate a python index file', action="store_true")
    parser.add_argument('-m', '--manifest', help='Generate a manifest file', nargs=1,
                        metavar=('mpdfile'))
    parser.add_argument('-s', '--split', help='Split MP4 file into fragments', nargs=1,
                        metavar=('mp4file'))
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
