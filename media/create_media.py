#!/usr/bin/env python
#
# This script will encode the given input stream at multiple bitrates and create a DASH
# compatible fragmented file. Optionally it can also create encrypted versions of these
# DASH streams.
#
# Example of creating a clear and encrypted version of Big Buck Bunny:
#
# test -e "BigBuckBunny.mp4" || curl -o "BigBuckBunny.mp4" "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
# python create_media.py -i "BigBuckBunny.mp4" -p bbb --kid '1ab45440532c439994dc5c5ad9584bac' -o output
#
# In the above example, only the Key ID (kid) is supplied but no key. When no key is supplied
# this script will use the PlayReady key generation algorithm with the test key seed.
#
#
# To use different keys for the audio and video adaptation sets, provide two KIDs (and keys)
# on the command line.
#
# test -e tearsofsteel.mp4 || curl -o tearsofsteel.mp4 'http://profficialsite.origin.mediaservices.windows.net/aac2a25c-0dbc-46bd-be5f-68f3df1fc1f6/tearsofsteel_1080p_60s_24fps.6000kbps.1920x1080.h264-8b.2ch.128kbps.aac.mp4'
# python create_media.py -i "tearsofsteel.mp4" -p tears --kid a2c786d0-f9ef-4cb3-b333-cd323a4284a5 db06a8fe-ec16-4de2-9228-2c71e9b856ab -o tears
#
#
# A more complex example, where the audio track is replaced with a 5.1 version before encoding
#
# curl -o ToS-4k-1920.mov http://ftp.nluug.nl/pub/graphics/blender/demo/movies/ToS/ToS-4k-1920.mov
# curl -o ToS-Dolby-5.1.ac3 'http://media.xiph.org/tearsofsteel/Surround-TOS_DVDSURROUND-Dolby%205.1.ac3'
# ffmpeg -i ToS-4k-1920.mov -i ToS-Dolby-5.1.ac3 -c:v copy -c:a copy -map 0:v:0 -map 1:a:0 ToS-4k-1920-Dolby.5.1.mp4
# python create_media.py -d 61 -i ToS-4k-1920-Dolby.5.1.mp4 -p tears --kid a2c786d0-f9ef-4cb3-b333-cd323a4284a5 db06a8fe-ec16-4de2-9228-2c71e9b856ab -o tears-v2
#
#
# ffmpeg was compiled with the following options:
# ./configure --enable-gpl --enable-version3 --enable-nonfree --enable-libx264 --enable-libvorbis --enable-libvpx
#


import argparse
import collections
import json
import logging
import os
import math
import random
import shutil
import subprocess
import sys
import tempfile

sys.path.append(os.path.join(os.path.dirname(__file__),'..', 'src'))

import drm
import mp4
import segment

class InitialisationVector(drm.KeyMaterial):
    length = 8

EncodedRepresentation = collections.namedtuple('EncodedRepresentation', 'source contentType index')

class DashMediaCreator(object):
    # each item is (width, height, bitrate)
    BITRATE_LADDER= [
        (384, 216, 230),
        (512, 288, 450),
        (640, 360, 690),
        (768, 432, 800),
        (1024, 576, 1250),
        (1280, 720, 2204),
        (1920, 1080, 3600),
    ]
    
    XML_TEMPLATE="""<?xml version="1.0" encoding="UTF-8"?>
    <GPACDRM type="CENC AES-CTR">
      <CrypTrack trackID="{track_id:d}" IsEncrypted="1" IV_size="{iv_size:d}"
        first_IV="{iv}" saiSavedBox="senc">
        <key KID="0x{kid}" value="0x{key}" />
      </CrypTrack>
    </GPACDRM>
    """

    def __init__(self, options):
        self.options = options

        # Duration of a segment (in frames)
        self.frame_segment_duration = self.options.segment_duration * self.options.framerate
        
        # The MP4 timescale to use for video
        self.timescale = self.options.framerate * 10

        self.media_info = {
            "keys": [],
            "streams": [
                {
                    "prefix": self.options.prefix,
                    "title":""
                }
            ],
            "files": []
        }

    def encode_all(self, srcfile):
        first = True
        for width, height, bitrate in self.BITRATE_LADDER:
            self.encode_representation(srcfile, width, height, bitrate, first)
            first = False

    def encode_representation(self, srcfile, width, height, bitrate, first):
        """Encode the stream and check key frames are in the correct place"""
        destdir = os.path.join(self.options.destdir, str(bitrate))
        dest = os.path.join(destdir, self.options.prefix+'.mp4')
        if os.path.exists(dest):
            return
        if not os.path.exists(destdir):
            os.makedirs(destdir)
        if ':' in self.options.aspect:
            n,d = self.options.aspect.split(':')
            aspect = float(n) / float(d)
        else:
            aspect = float(self.options.aspect)
        height = 4 * (int(float(height) / aspect) // 4)
        print "{}: {}x{} {}Kbps".format(dest, width, height, bitrate)
        profile="baseline"
        cbr=(bitrate *10) // 12
        minrate=(bitrate * 10) // 14
        level=3.1
        # buffer_size is set to 75% of VBV limit
        buffer_size=4000
        if width > 640:
	    profile="main"
        if height > 720:
	    profile="high"
	    level=4.0
	    # buffer_size is set to 75% of VBV limit
	    buffer_size=25000
        keyframes=map(str, range(0, self.options.duration+self.options.segment_duration,
                                 self.options.segment_duration))
        keyframes = ','.join(keyframes)
        ffmpeg_args = [
            "ffmpeg",
            "-ss", "5",
            "-ec", "deblock",
	    "-i",  srcfile,
	    "-vf",
            "drawtext='fontfile=/usr/share/fonts/truetype/freefont/FreeSansBold.ttf:fontsize=48:text='"+str(bitrate)+"'Kbps:x=(w-tw)/2:y=h-(2*lh):fontcolor=white:box=1:boxcolor=0x000000@0.7'",
            "-video_track_timescale", str(self.timescale),
	    "-map", "0:v:0",
        ]
        if first:
            ffmpeg_args += [
                "-map", "0:a:0",
                "-map", "0:a:0",
            ]
        ffmpeg_args += [
	    "-codec:v", "libx264",
            "-aspect", self.options.aspect,
            "-profile:v", profile,
            "-level:v", str(level),
            "-field_order", "progressive",
            "-bufsize", '{:d}k'.format(buffer_size),
            "-maxrate", '{:d}k'.format(bitrate),
            "-minrate", '{:d}k'.format(minrate),
            "-b:v", "{:d}k".format(cbr),
            "-pix_fmt", "yuv420p",
            "-s", "{:d}x{:d}".format(width, height),
            "-x264opts", "keyint={:d}:videoformat=pal".format(self.frame_segment_duration),
            "-flags", "+cgop+global_header",
            "-flags2", "-local_header",
            "-g", str(self.frame_segment_duration),
            "-sc_threshold", "0",
	    "-force_key_frames", keyframes,
	    "-y",
            "-t", str(self.options.duration),
            "-threads", "0",
        ]
        if first:
            ffmpeg_args += [
	        "-codec:a:0", "aac",
                "-b:a:0", "96k",
                "-ac:a:0", "2",
                "-strict", "-2",
                "-codec:a:1", "eac3",
                "-b:a:1", "320k",
                "-ac:a:1", "6",
            ]
        ffmpeg_args += [ dest ]
        print(ffmpeg_args)
        subprocess.check_call(ffmpeg_args)

        print 'Checking key frames in '+dest
        ffmpeg_args = [
            "ffprobe",
            "-show_frames",
            "-print_format", "compact",
            dest
        ]
        idx=0
        probe = subprocess.check_output(ffmpeg_args, stderr=subprocess.STDOUT,
                                        universal_newlines=True)
        for line in probe.splitlines():
            info = {}
            if not '|' in line:
                continue
            for i in line.split('|'):
                if not '=' in i:
                    continue
                k,v = i.split('=')
                info[k] = v
            try:
                if info['media_type'] == 'video':
                    if (idx % self.frame_segment_duration) == 0 and info['key_frame'] != '1':
                        print info
                        raise ValueError('Frame {} should be a key frame'.format(idx))
                    idx += 1
            except KeyError:
                pass

    def create_file_from_fragments(self, dest_filename, moov, prefix):
        print(dest_filename, moov, prefix)
        if not os.path.exists(moov):
            raise IOError('MOOV not found: {}'.format(moov))
        print dest_filename
        with open(dest_filename, "wb") as dest:
            sys.stdout.write('I')
            sys.stdout.flush()
            with open(moov, "rb") as src:
                shutil.copyfileobj(src, dest)
            segment=1
            while True:
                moof = "{}{:03d}.mp4".format(prefix, segment)
                if not os.path.exists(moof):
                    break
                sys.stdout.write('f')
                sys.stdout.flush()
                with open(moof, "rb") as src:
                    shutil.copyfileobj(src, dest)
                os.remove(moof)
                segment += 1
            sys.stdout.write('\n')

    def package_all(self):
        destdir = os.path.abspath(self.options.destdir)
        bitrates = map(lambda l: l[2], self.BITRATE_LADDER)
        source_files=[]
        nothing_to_do = True
        for idx in range(len(bitrates)):
            dest_file = os.path.join(destdir, self.destination_filename('v', idx+1, False))
            if not os.path.exists(dest_file):
                nothing_to_do = False
        dest_file = os.path.join(destdir, self.destination_filename('a', 1, False))
        if not os.path.exists(dest_file):
            nothing_to_do = False
        dest_file = os.path.join(destdir, self.destination_filename('a', 2, False))
        if not os.path.exists(dest_file):
            nothing_to_do = False
        if nothing_to_do:
            return

        for index, bitrate in enumerate(bitrates):
            source_files.append(EncodedRepresentation(
                source=os.path.join(destdir, str(bitrate),
                                    self.options.prefix + ".mp4#video"),
                contentType='v',
                index=index+1))
        # Add AAC audio track
        source_files.append(EncodedRepresentation(
            source = os.path.join(destdir, str(bitrates[0]),
                                  self.options.prefix + ".mp4#trackID=2:role=main"),
            contentType='a',
            index=1))
        # Add E-AC3 audio track
        source_files.append(EncodedRepresentation(
            source = os.path.join(destdir, str(bitrates[0]),
                                  self.options.prefix + ".mp4#trackID=3:role=alternate"),
            contentType='a',
            index=2))

        self.package_sources(source_files)

    def package_sources(self, source_files):
        destdir = os.path.abspath(self.options.destdir)
        tmpdir = os.path.join(destdir, "dash")
        if not os.path.exists(tmpdir):
            os.makedirs(tmpdir)
        bs_switching = 'inband' if self.options.avc3 else 'merge'
        mp4box_args = [
            "MP4Box",
            "-dash", str(self.options.segment_duration * self.timescale),
            "-frag", str(self.options.segment_duration * self.timescale),
            "-dash-scale", str(self.timescale),
            "-rap",
            "-fps", str(self.options.framerate),
            "-frag-rap",
            "-profile", "live",
            "-profile-ext", "urn:dvb:dash:profile:dvbdash:2014",
            "-bs-switching", bs_switching,
            "-segment-ext", "mp4",
            "-segment-name", 'dash_$RepresentationID$_$number%03d$$Init=init$',
            "-out", "manifest",
        ]
        mp4box_args += map(lambda f: f.source, source_files)
        print mp4box_args
        cwd = os.getcwd()
        os.chdir(tmpdir)
        subprocess.check_call(mp4box_args)
        os.chdir(cwd)
        subprocess.call(["ls", "-lR", tmpdir])

        for idx, source in enumerate(source_files):
            prefix = os.path.join(tmpdir, 'dash_{:d}_'.format(idx+1))
            source, contentType, num = source
            dest_file = self.destination_filename(contentType, num, False)
            self.media_info['files'].append(dest_file)
            dest_file = os.path.join(destdir, dest_file)
            moov = os.path.join(tmpdir, 'manifest_set1_init.mp4')
            if os.path.exists(prefix+'init.mp4'):
                moov = prefix+'init.mp4'
            print(dest_file, moov, prefix)
            if os.path.exists(dest_file):
                continue
            self.create_file_from_fragments(dest_file, moov, prefix)
            if os.path.exists(prefix+'init.mp4'):
                os.remove(moov)

    def destination_filename(self, contentType, index, encrypted):
        enc = '_enc' if encrypted else ''
        return '{}_{}{:d}{}.mp4'.format(self.options.prefix, contentType, index, enc)
        
    def encrypt_all(self):
        destdir = os.path.abspath(self.options.destdir)
        kid = self.options.kid
        assert isinstance(kid, list)
        assert len(kid) > 0
        kids = {
            'v': drm.KeyMaterial(value=kid[0]),
            'a': drm.KeyMaterial(value=kid[-1])
        }
        if self.options.key:
            assert isinstance(self.options.key, list)
            keys = {
                'v': drm.KeyMaterial(value=self.options.key[0]),
                'a': drm.KeyMaterial(value=self.options.key[-1]),
            }
        else:
            keys = {}
            for k,v in kids.iteritems():
                keys[k] = drm.KeyMaterial(raw=drm.PlayReady.generate_content_key(v.raw))
                print 'Using key {} for kid {}'.format(keys[k].hex, v.hex)
        for k in kids.keys():
            item = {
                "kid": kids[k].hex,
                "computed": not self.options.key
            }
            if not item['computed']:
                item["key"] = keys[k].hex
            self.media_info["keys"].append(item)
        files = []
        for idx in range(len(self.BITRATE_LADDER)):
            files.append(('v', idx+1))
        files.append(('a', 1))
        files.append(('a', 2))
        for contentType, index in files:
            src_file = self.destination_filename(contentType, index, False)
            src_file = os.path.join(destdir, src_file)
            dest_file = self.destination_filename(contentType, index, True)
            self.media_info['files'].append(dest_file)
            dest_file = os.path.join(destdir, dest_file)
            iv = InitialisationVector(hex='{:016x}'.format(random.getrandbits(64)))
            self.encrypt_representation(src_file, dest_file, kids[contentType],
                                        keys[contentType], iv)

    def encrypt_representation(self, source, destfile, kid, key, iv):
        if os.path.exists(destfile):
            return
        try:
            tmpdir = tempfile.mkdtemp()
            self.build_encrypted_file(source, destfile, kid, key, iv, tmpdir)
        finally:
            try:
                shutil.rmtree(tmpdir)
            except (Exception) as ex:
                print(ex)

    def build_encrypted_file(self, source, dest_filename, kid, key, iv, tmpdir):
        representation = self.parse_representation(source)
        basename, ext = os.path.splitext(os.path.split(source)[1])
        moov_filename = os.path.join(tmpdir, basename+'-moov-enc.mp4')
        xmlfile = os.path.join(tmpdir,"drm.xml")
        with open(xmlfile, 'w') as xml:
            xml.write(self.XML_TEMPLATE.format(kid=kid.hex, key=key.hex, iv=iv.hex,
                                               iv_size=iv.length,
                                               track_id=representation.track_id))

        # MP4Box does not appear to be able to encrypt and fragment in one
        # stage, so first encrypt the media and then fragment it afterwards
        args = ["MP4Box", "-crypt", xmlfile, "-out", moov_filename]
        if fps:
            args += ["-fps", str(fps)]
        args.append(source)
        print(args)
        rv = subprocess.check_call(args)

        prefix = os.path.join(tmpdir, "dash_enc_")
        args = ["MP4Box",
                "-dash", str(self.options.segment_duration * 1000),
                "-frag", str(self.options.segment_duration * 1000),
                "-segment-ext", "mp4",
                "-segment-name", 'dash_enc_$number%03d$$Init=init$',
                "-profile", "live",
                "-frag-rap",
                "-fps", str(self.options.framerate),
                "-timescale", str(self.timescale),
                "-rap",
                "-out", "manifest",
                moov_filename
        ]
        print(args)
        cwd = os.getcwd()
        os.chdir(tmpdir)
        rv = subprocess.check_call(args)
        os.chdir(cwd)
        moov = prefix + "init.mp4"
        subprocess.call(["ls", tmpdir])
        self.create_file_from_fragments(dest_filename, moov, prefix)

    def parse_representation(self, filename):
        parser = mp4.IsoParser()
        print('Parse %s' % filename)
        atoms = parser.walk_atoms(filename)
        verbose = 2 if self.options.verbose else 0
        if verbose:
            print('Parse {0}'.format(filename))
        return segment.Representation.create(filename=filename.replace('\\','/'),
                                             atoms=atoms, verbose=verbose)

def gcd(x,y):
    while y:
        x,y = y, x % y
    return x

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description='DASH encoding and packaging')
    ap.add_argument('--duration', '-d', help='Stream duration (in seconds) (0=auto)',
                    type=int, default=0)
    ap.add_argument('--aspect', help='Aspect ratio (default=same as source)')
    ap.add_argument('--avc3', help='Use in-band (AVC3 format) init segments', action="store_true")
    ap.add_argument('--frag', help='Fragment duration (in seconds)', type=int,
                    dest='segment_duration', default=4)
    ap.add_argument('--fps', help='Frames per second (0=auto)', type=int,
                    dest='framerate', default=0)
    ap.add_argument('--input', '-i', help='Input audio/video file', required=True, dest='source')
    ap.add_argument('--kid', help='Key ID', nargs="*")
    ap.add_argument('--key', help='Encryption Key', nargs="*")
    ap.add_argument('-v', '--verbose', help='Verbose mode', action="store_true")
    ap.add_argument('--output', '-o', help='Output directory', dest='destdir', required=True)
    ap.add_argument('--prefix', '-p', help='Prefix for output files', required=True)
    args = ap.parse_args()

    info = subprocess.check_output([
        "ffprobe",
        "-v", "0",
        "-of", "json",
        "-show_format",
        "-show_streams",
        args.source
    ])

    info = json.loads(info)

    if not args.aspect:
        for s in info["streams"]:
            if s["codec_type"] != "video":
                continue
            try:
                args.aspect = s["display_aspect_ratio"]
            except KeyError:
                width = s["width"]
                height = s["height"]
                m = gcd(width, height)
                width /= m
                height /= m
                args.aspect = '{0}:{1}'.format(width, height)

    if args.duration == 0:
        args.duration = math.floor(float(info["format"]["duration"]))
    args.duration = int((args.duration // args.segment_duration) * args.segment_duration)

    if args.framerate == 0:
        for s in info["streams"]:
            try:
                fps = s["avg_frame_rate"]
                if '/' in fps:
                    n,d = fps.split('/')
                    if d == 0:
                        continue
                    fps = int(round(float(n) / float(d)))
                else:
                    fps = int(fps)
                args.framerate = fps
                break
            except KeyError:
                pass

    #logging.basicConfig()
    mp4_log = logging.getLogger('mp4')
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s: %(message)s'))
    mp4_log.addHandler(ch)
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        mp4_log.setLevel(logging.DEBUG)
    if not os.path.exists(args.destdir):
        os.makedirs(args.destdir)

    dmc = DashMediaCreator(args)
    dmc.encode_all(args.source)
    dmc.package_all()
    if args.kid:
        dmc.encrypt_all()
    mi = os.path.join(args.destdir, args.prefix+".json")
    with open(mi, 'w') as f:
        json.dump(dmc.media_info, f)

