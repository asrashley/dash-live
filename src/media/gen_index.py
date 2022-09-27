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

import argparse
import fnmatch
import io
import os

from mpeg.mp4 import IsoParser
from mpeg.dash.representation import Representation
from utils.date_time import toIsoDuration

class GenerateIndex(object):
    def __init__(self, args):
        self.args = args

    def create_index_file(self, filename):
        rep = self.create_representation(filename)
        if self.args.codec:
            codec_src = self.create_representation(self.args.codec[0])
            rep.codecs = codec_src.codecs
            if rep.contentType == 'video':
                rep.height = codec_src.height
                rep.width = codec_src.width
                try:
                    rep.frameRate = codec_src.frameRate
                except AttributeError:
                    pass
            else:
                rep.sampleRate = codec_src.sampleRate
                rep.numChannels = codec_src.numChannels
        if self.args.manifest:
            self.generate_manifest(filename, rep)
        if self.args.split:
            ext = 'm4a' if repr.contentType == 'audio' else 'm4v'
            src_file = io.FileIO(filename, 'rb')
            for idx, seg in enumerate(rep.segments):
                if idx == 0:
                    dst_filename = os.path.join(self.args.split[0], 'init.%s' % ext)
                else:
                    dst_filename = os.path.join(self.args.split[0], '%05d.%s' % (idx, ext))
                print dst_filename
                with io.FileIO(dst_filename, 'wb') as dst_file:
                    src_file.seek(seg.pos)
                    data = src_file.read(seg.size)
                    dst_file.write(data)
            src_file.close()
        if self.args.index:
            print('Creating {0}.py'.format(rep.id))
            with open(rep.id + '.py', 'wt') as dest:
                dest.write('from mpeg.dash.representation import Representation\n')
                dest.write('representation=')
                dest.write(str(rep))
                dest.write('\n')

    def create_representation(self, filename):
        print filename
        parser = IsoParser()
        atoms = parser.walk_atoms(filename)
        verbose = 2 if self.args.debug else 1
        return Representation.create(filename=filename.replace('\\', '/'),
                                     atoms=atoms, verbose=verbose)

    def generate_manifest(self, filename, rep):
        print('Creating manifest ' + self.args.manifest[0])
        with open(self.args.manifest[0], 'wt') as dest:
            self._generate_manifest(filename, rep, dest)

    def _generate_manifest(self, filename, rep, dest):
        dest.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        dest.write('<MPD xmlns="urn:mpeg:dash:schema:mpd:2011"')
        dest.write(' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"')
        dest.write(' mediaPresentationDuration="%s"' % toIsoDuration(
            rep.mediaDuration / rep.timescale))
        dest.write(' minBufferTime="PT10S"')
        dest.write(' profiles="urn:mpeg:dash:profile:isoff-on-demand:2011" type="static"')
        dest.write(' xsi:schemaLocation="urn:mpeg:dash:schema:mpd:2011')
        dest.write(' http://standards.iso.org/ittf/PubliclyAvailableStandards/MPEG-DASH_schema_files/DASH-MPD.xsd">\n')
        dest.write(' <Period start="PT0S" duration="%s">\n' % toIsoDuration(
            rep.mediaDuration / rep.timescale))
        if rep.contentType == 'audio':
            ext = 'm4a'
            mimeType = 'audio/mp4'
        else:
            ext = 'm4v'
            mimeType = 'video/mp4'
        dest.write('  <AdaptationSet contentType="%s" group="1" lang="%s"' % (
            rep.contentType, rep.language))
        dest.write(' mimeType="%s" segmentAlignment="true"' % (mimeType))
        dest.write(' subsegmentAlignment="true" subsegmentStartsWithSAP="1">\n')
        try:
            dest.write(
                '   <Representation audioSamplingRate="%d" bandwidth="%d" codecs="%s" id="%s">\n' % (
                    rep.sampleRate, rep.bitrate, rep.codecs, rep.id))
        except AttributeError:
            dest.write('   <Representation frameRate="%d" bandwidth="%d"' % (
                rep.frameRate, rep.bitrate))
            dest.write(' codecs="%s" id="%s" height="%d" width="%d">\n' % (
                rep.codecs, rep.id, rep.height, rep.width))
        if self.args.split:
            dest.write('     <SegmentTemplate presentationTimeOffset="0" timescale="%d" startNumber="1" ' % (rep.timescale))
            dest.write('initialization="$RepresentationID$/init.%s"' % (ext))
            dest.write(' media="$RepresentationID$/$Number%%05d$.%s"' % (ext))
            dest.write(' duration="%d"/>\n' % (rep.segment_duration))
        else:
            dest.write('     <BaseURL>%s</BaseURL>\n' % filename)
            dest.write('     <SegmentList duration="%d" timescale="%d">\n' % (
                rep.segment_duration, rep.timescale))
            dest.write('       <Initialization range="%d-%d"/>\n' % (
                rep.segments[0].pos, rep.segments[0].pos + rep.segments[0].size - 1))
            for seg in rep.segments[1:]:
                dest.write('       <SegmentURL d="%d" mediaRange="%d-%d"/>\n' % (
                    seg.duration, seg.pos, seg.pos + seg.size - 1))
            dest.write('     </SegmentList>\n')
        dest.write('   </Representation>\n')
        dest.write('  </AdaptationSet>\n')
        dest.write(' </Period>\n')
        dest.write('</MPD>\n')

    @classmethod
    def main(cls):
        parser = argparse.ArgumentParser(description='MP4 parser and index generation')
        parser.add_argument('-d', '--debug', action="store_true")
        parser.add_argument('-c', '--codec', help='MP4 file that contains codec information',
                            nargs=1, metavar=('mp4file'))
        parser.add_argument('-i', '--index', help='Generate a python index file',
                            action="store_true")
        parser.add_argument('-m', '--manifest', help='Generate a manifest file', nargs=1,
                            metavar=('mpdfile'))
        parser.add_argument('-s', '--split', help='Split MP4 file into fragments', nargs=1,
                            metavar=('mp4file'))
        parser.add_argument('mp4file', help='Filename of MP4 file', nargs='+', default=None)
        args = parser.parse_args()

        gen = GenerateIndex(args)
        for fname in args.mp4file:
            if '*' in fname or '?' in fname:
                directory = os.path.dirname(fname)
                if directory == '':
                    directory = '.'
                files = os.listdir(directory)
                for filename in fnmatch.filter(files, fname):
                    gen.create_index_file(filename)
            else:
                gen.create_index_file(fname)


if __name__ == "__main__":
    GenerateIndex.main()
