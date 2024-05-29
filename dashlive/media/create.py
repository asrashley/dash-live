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

#
# This script will encode the given input stream at multiple bitrates and create a DASH
# compatible fragmented file. Optionally it can also create encrypted versions of these
# DASH streams.
#
# Example of creating a clear and encrypted version of Big Buck Bunny:
#
# test -e "BigBuckBunny.mp4" || curl -o "BigBuckBunny.mp4" \
#    "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
# python -m dashlive.media.create -i "BigBuckBunny.mp4" -p bbb \
#    --font /usr/share/fonts/truetype/freefont/FreeSansBold.ttf \
#    --kid '1ab45440532c439994dc5c5ad9584bac' -o output
#
# In the above example, only the Key ID (kid) is supplied but no key. When no key is supplied
# this script will use the PlayReady key generation algorithm with the test key seed.
#
#
# To use different keys for the audio and video adaptation sets, provide two KIDs (and keys)
# on the command line.
#
# test -e tearsofsteel.mp4 || curl -o tearsofsteel.mp4 \
#    'http://profficialsite.origin.mediaservices.windows.net/aac2a25c-0dbc-46bd-be5f-68f3df1fc1f6/tearsofsteel_1080p_60s_24fps.6000kbps.1920x1080.h264-8b.2ch.128kbps.aac.mp4'
#
# python -m dashlive.media.create -i "tearsofsteel.mp4" -p tears \
#    --kid a2c786d0-f9ef-4cb3-b333-cd323a4284a5 db06a8fe-ec16-4de2-9228-2c71e9b856ab -o tears
#
#
# A more complex example, where the audio track is replaced with a 5.1 version before encoding
#
# curl -o ToS-4k-1920.mov http://ftp.nluug.nl/pub/graphics/blender/demo/movies/ToS/ToS-4k-1920.mov
# curl -o ToS-Dolby-5.1.ac3 'http://media.xiph.org/tearsofsteel/Surround-TOS_DVDSURROUND-Dolby%205.1.ac3'
# ffmpeg -i ToS-4k-1920.mov -i ToS-Dolby-5.1.ac3 -c:v copy -c:a copy -map 0:v:0 -map 1:a:0 ToS-4k-1920-Dolby.5.1.mp4
# python -m dashlive.media.create -d 61 -i ToS-4k-1920-Dolby.5.1.mp4 -p tears --surround \
#    --kid a2c786d0-f9ef-4cb3-b333-cd323a4284a5 db06a8fe-ec16-4de2-9228-2c71e9b856ab -o tears-v2
#
#
# ffmpeg was compiled with the following options:
# ./configure --enable-gpl --enable-version3 --enable-nonfree --enable-libx264 --enable-libvorbis --enable-libvpx
#

import argparse
from dataclasses import dataclass, field, InitVar
import json
import logging
import os
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import NamedTuple

from dashlive.drm.keymaterial import KeyMaterial
from dashlive.drm.playready import PlayReady
from dashlive.mpeg import mp4
from dashlive.mpeg.codec_strings import codec_data_from_string
from dashlive.mpeg.dash.representation import Representation

class EncodedRepresentation(NamedTuple):
    source: Path
    contentType: str
    index: int

class InitialisationVector(KeyMaterial):
    length = 8

class VideoEncodingParameters(NamedTuple):
    width: int
    height: int
    bitrate: int
    codecString: str | None

@dataclass
class MediaCreateOptions:
    aspect: str | None
    avc3: bool
    duration: int
    font: str
    framerate: int
    kid: list[str]
    key: list[str]
    segment_duration: float
    surround: bool
    verbose: bool
    prefix: str
    source: str
    output: InitVar[str]
    aspect_ratio: float = field(init=False)
    destdir: Path = field(init=False)

    def __post_init__(self, output: str) -> None:
        self.destdir = Path(output).resolve(strict=True)
        if self.aspect is not None:
            self.set_aspect(self.aspect)

    def set_aspect(self, aspect: str) -> None:
        self.aspect = aspect
        if ':' in aspect:
            n, d = aspect.split(':')
            self.aspect_ratio = float(n) / float(d)
        else:
            self.aspect_ratio = float(aspect)


class DashMediaCreator:
    BITRATE_LADDER: list[VideoEncodingParameters] = [
        VideoEncodingParameters(1920, 1080, 8600, "avc1.64002A"),
        VideoEncodingParameters(1280, 720, 4900, "avc1.640020"),
        VideoEncodingParameters(1280, 720, 3200, "avc1.64001F"),
        VideoEncodingParameters(1024, 576, 2300, "avc1.64001F"),
        VideoEncodingParameters(800, 450, 1650, "avc1.64001E"),
        VideoEncodingParameters(640, 360, 1150, "avc1.64001E"),
        VideoEncodingParameters(512, 288, 800, "avc1.640015"),
        VideoEncodingParameters(352, 198, 500, "avc1.640014"),
        VideoEncodingParameters(320, 180, 300, "avc1.640014"),
        VideoEncodingParameters(320, 180, 200, "avc1.4D4014"),
    ]

    XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
    <GPACDRM type="CENC AES-CTR">
      <CrypTrack trackID="{track_id:d}" IsEncrypted="1" IV_size="{iv_size:d}"
        first_IV="{iv}" saiSavedBox="senc">
        <key KID="0x{kid}" value="0x{key}" />
      </CrypTrack>
    </GPACDRM>
    """

    def __init__(self, options: MediaCreateOptions) -> None:
        self.options = options
        self.frame_segment_duration = None
        self.timescale = None

        self.media_info = {
            "keys": [],
            "streams": [
                {
                    "directory": self.options.prefix,
                    "title": "",
                    "files": []
                }
            ]
        }

    def encode_all(self) -> None:
        first = True
        for width, height, bitrate, codec in self.BITRATE_LADDER:
            self.encode_representation(width, height, bitrate, codec, first)
            first = False

    def encode_representation(self, width: int, height: int,
                              bitrate: int, codec: str | None, first: bool) -> None:
        """
        Encode the stream and check key frames are in the correct place
        """
        destdir = self.options.destdir / f'{bitrate}'
        dest = destdir / f'{self.options.prefix}.mp4'
        if dest.exists():
            return
        destdir.mkdir(parents=True, exist_ok=True)
        height = 4 * (int(float(height) / self.options.aspect_ratio) // 4)
        logging.debug("%s: %dx%d %d Kbps", dest, width, height, bitrate)
        cbr = (bitrate * 10) // 12
        minrate = (bitrate * 10) // 14
        vcodec = "libx264"
        # buffer_size is set to 75% of VBV limit
        buffer_size = 4000
        if codec is None:
            profile = "baseline"
            level = 3.1
            if height > 720:
                profile = "high"
                level = 4.0
                # buffer_size is set to 75% of VBV limit
                buffer_size = 25000
            elif width > 640:
                profile = "main"
        else:
            codec_data = codec_data_from_string(codec)
            profile = codec_data.profile_string()
            level = codec_data.level
            if level >= 4.0:
                buffer_size = 25000
            if codec_data.codec == 'h.265':
                vcodec = 'hevc'
        keyframes = []
        pos = 0
        end = self.options.duration + self.options.segment_duration
        while pos < end:
            keyframes.append(f'{pos}')
            pos += self.options.segment_duration
        keyframes = ','.join(keyframes)
        ffmpeg_args = [
            "ffmpeg",
            "-ss", "5",
            "-ec", "deblock",
            "-i", self.options.source,
            "-video_track_timescale", str(self.timescale),
            "-map", "0:v:0",
        ]
        if self.options.font is not None:
            drawtext = ':'.join([
                'fontfile=' + self.options.font,
                'fontsize=48',
                'text=' + str(bitrate) + ' Kbps',
                'x=(w-tw)/2',
                'y=h-(2*lh)',
                'fontcolor=white',
                'box=1',
                'boxcolor=0x000000@0.7'])
            ffmpeg_args.append("-vf")
            ffmpeg_args.append(f"drawtext={drawtext}")
        if first:
            ffmpeg_args += ["-map", "0:a:0"]
            if self.options.surround:
                ffmpeg_args += ["-map", "0:a:0"]
        ffmpeg_args += [
            "-codec:v", vcodec,
            "-aspect", self.options.aspect,
            "-profile:v", profile,
            "-level:v", str(level),
            "-field_order", "progressive",
            "-bufsize", f'{buffer_size:d}k',
            "-maxrate", f'{bitrate:d}k',
            "-minrate", f'{minrate:d}k',
            "-b:v", f"{cbr:d}k",
            "-pix_fmt", "yuv420p",
            "-s", f"{width:d}x{height:d}",
            "-x264opts", f"keyint={self.frame_segment_duration:d}:videoformat=pal",
            "-flags", "+cgop+global_header",
            "-flags2", "-local_header",
            "-g", str(self.frame_segment_duration),
            "-sc_threshold", "0",
            "-force_key_frames", keyframes,
            "-y",
            "-t", str(self.options.duration),
            "-threads", "0",
        ]
        if self.options.framerate:
            ffmpeg_args += ["-r", str(self.options.framerate)]
        if first:
            ffmpeg_args += [
                "-codec:a:0", "aac",
                "-b:a:0", "96k",
                "-ac:a:0", "2",
                "-strict", "-2",
            ]
            if self.options.surround:
                ffmpeg_args += [
                    "-codec:a:1", "eac3",
                    "-b:a:1", "320k",
                    "-ac:a:1", "6",
                ]
        ffmpeg_args.append(str(dest))
        logging.debug(ffmpeg_args)
        subprocess.check_call(ffmpeg_args)

        logging.info('Checking key frames in %s', dest)
        ffmpeg_args = [
            "ffprobe",
            "-show_frames",
            "-print_format", "compact",
            str(dest)
        ]
        idx = 0
        probe = subprocess.check_output(
            ffmpeg_args, stderr=subprocess.STDOUT, text=True)
        for line in probe.splitlines():
            info = {}
            if '|' not in line:
                continue
            for i in line.split('|'):
                if '=' not in i:
                    continue
                k, v = i.split('=')
                info[k] = v
            try:
                if info['media_type'] == 'video':
                    if (idx % self.frame_segment_duration) == 0 and info['key_frame'] != '1':
                        logging.warning('Info: %s', info)
                        raise ValueError(f'Frame {idx} should be a key frame')
                    idx += 1
            except KeyError:
                pass

    def create_file_from_fragments(self, dest_filename: Path, moov: Path, prefix: str) -> None:
        logging.info('Create file "%s" moov="%s" prefix="%s"',
                     dest_filename, moov, prefix)
        if not moov.exists():
            raise OSError(f'MOOV not found: {moov}')
        with dest_filename.open("wb") as dest:
            if self.options.verbose:
                sys.stdout.write('I')
                sys.stdout.flush()
            with open(moov, "rb") as src:
                shutil.copyfileobj(src, dest)
            segment = 1
            while True:
                moof = f'{prefix}{segment:03d}.mp4'
                if not os.path.exists(moof):
                    break
                if self.options.verbose:
                    sys.stdout.write('f')
                    sys.stdout.flush()
                with open(moof, "rb") as src:
                    shutil.copyfileobj(src, dest)
                os.remove(moof)
                segment += 1
            if self.options.verbose:
                sys.stdout.write('\n')
        logging.info(r'Generated file %s', dest_filename)

    def package_all(self) -> bool:
        bitrates: list[int] = [br[2] for br in self.BITRATE_LADDER]
        source_files: list[EncodedRepresentation] = []
        nothing_to_do = True
        for idx in range(len(bitrates)):
            dest_file = self.options.destdir / self.destination_filename('v', idx + 1, False)
            if not dest_file.exists():
                nothing_to_do = False
        dest_file = self.options.destdir / self.destination_filename('a', 1, False)
        if not dest_file.exists():
            nothing_to_do = False
        dest_file = self.options.destdir / self.destination_filename('a', 2, False)
        if not dest_file.exists():
            nothing_to_do = False
        if nothing_to_do:
            return False

        for index, bitrate in enumerate(bitrates):
            src_file = self.options.destdir / f'{bitrate}' / f'{self.options.prefix}.mp4#video'
            source_files.append(EncodedRepresentation(
                source=src_file, contentType='v', index=(index + 1)))
        # Add AAC audio track
        src_file = self.options.destdir / f'{bitrates[0]}' / f'{self.options.prefix}.mp4#trackID=2:role=main'
        source_files.append(EncodedRepresentation(source=src_file, contentType='a', index=1))
        # Add E-AC3 audio track
        src_file = self.options.destdir / f'{bitrates[0]}' / f'{self.options.prefix}.mp4#trackID=3:role=alternate'
        source_files.append(EncodedRepresentation(source=src_file, contentType='a', index=2))

        self.package_sources(source_files)
        return True

    def package_sources(self, source_files: list[EncodedRepresentation]) -> None:
        tmpdir = self.options.destdir / "dash"
        tmpdir.mkdir(parents=True, exist_ok=True)
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
        mp4box_args += [str(f.source) for f in source_files]
        logging.debug('mp4box_args: %s', mp4box_args)
        cwd = os.getcwd()
        os.chdir(tmpdir)
        subprocess.check_call(mp4box_args)
        os.chdir(cwd)
        if self.options.verbose:
            subprocess.call(["ls", "-lR", tmpdir])

        for idx, source in enumerate(source_files):
            prefix = str(tmpdir / f'dash_{idx + 1}_')
            source, contentType, num = source
            dest_file = self.destination_filename(contentType, num, False)
            self.media_info['streams'][0]['files'].append(dest_file)
            dest_file = self.options.destdir / dest_file
            if dest_file.exists():
                logging.debug('File %s exists, skipping generation', dest_file)
                continue
            moov = tmpdir / 'manifest_set1_init.mp4'
            if os.path.exists(prefix + 'init.mp4'):
                moov = Path(prefix + 'init.mp4')
            logging.debug('Check for file: "%s"', dest_file)
            self.create_file_from_fragments(dest_file, moov, prefix)
            if os.path.exists(prefix + 'init.mp4'):
                os.remove(moov)

    def destination_filename(self, contentType: str, index: int, encrypted: bool) -> str:
        enc = '_enc' if encrypted else ''
        return f'{self.options.prefix}_{contentType}{index:d}{enc}.mp4'

    def create_key_ids(self) -> list[str]:
        rv = []
        for kid in self.options.kid:
            if kid == 'random':
                kid = os.urandom(KeyMaterial.length).encode('hex')
            rv.append(kid)
        return rv

    def encrypt_all(self) -> None:
        kids = self.create_key_ids()
        assert len(kids) > 0
        kid_map = {
            'v': KeyMaterial(hex=kids[0]),
            'a': KeyMaterial(hex=kids[-1])
        }
        if self.options.key:
            assert isinstance(self.options.key, list)
            key_map = {
                'v': KeyMaterial(hex=self.options.key[0]),
                'a': KeyMaterial(hex=self.options.key[-1]),
            }
        else:
            key_map = {}
            for k, v in kid_map.items():
                key_map[k] = KeyMaterial(raw=PlayReady.generate_content_key(v.raw))
                logging.debug('Using key %s for kid %s', key_map[k].hex, v.hex)
        media_keys = {}
        for k, v in kid_map.items():
            item = {
                "kid": v.hex,
                "computed": not self.options.key
            }
            if not item['computed']:
                item["key"] = key_map[k].hex
            media_keys[v.hex] = item
        for item in media_keys.values():
            self.media_info["keys"].append(item)
        self.media_info["keys"].sort(key=lambda item: item['kid'])
        files = []
        for idx in range(len(self.BITRATE_LADDER)):
            files.append(('v', idx + 1))
        files.append(('a', 1))
        files.append(('a', 2))
        for contentType, index in files:
            src_file = self.options.destdir / self.destination_filename(contentType, index, False)
            dest_file = self.destination_filename(contentType, index, True)
            self.media_info['streams'][0]['files'].append(dest_file)
            iv = InitialisationVector(raw=os.urandom(8))
            self.encrypt_representation(
                src_file, self.options.destdir / dest_file, kid_map[contentType],
                key_map[contentType], iv)

    def encrypt_representation(
            self, source: Path, destfile: Path,
            kid: KeyMaterial, key: KeyMaterial, iv: InitialisationVector) -> None:
        if destfile.exists():
            logging.debug('File "%s" already exists, nothing to do', destfile)
            return
        try:
            tmpdir = Path(tempfile.mkdtemp())
            self.build_encrypted_file(source, destfile, kid, key, iv, tmpdir)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def build_encrypted_file(
            self, source: Path, dest_filename: Path,
            kid: KeyMaterial, key: KeyMaterial, iv: InitialisationVector,
            tmpdir: Path) -> None:
        representation = self.parse_representation(str(source))
        basename = source.stem
        moov_filename = tmpdir / f'{basename}-moov-enc.mp4'
        xmlfile = tmpdir / "drm.xml"
        with xmlfile.open('wt', encoding='utf-8') as xml:
            xml.write(self.XML_TEMPLATE.format(kid=kid.hex, key=key.hex, iv=iv.hex,
                                               iv_size=iv.length,
                                               track_id=representation.track_id))

        # MP4Box does not appear to be able to encrypt and fragment in one
        # stage, so first encrypt the media and then fragment it afterwards
        args = [
            "MP4Box",
            "-crypt", str(xmlfile),
            "-out", str(moov_filename),
        ]
        if self.options.framerate:
            args += ["-fps", str(self.options.framerate)]
        args.append(str(source))
        logging.debug('MP4Box arguments: %s', args)
        subprocess.check_call(args)

        prefix = str(tmpdir / "dash_enc_")
        args = [
            "MP4Box",
            "-dash", str(self.options.segment_duration * self.timescale),
            "-frag", str(self.options.segment_duration * self.timescale),
            "-segment-ext", "mp4",
            "-segment-name", 'dash_enc_$number%03d$$Init=init$',
            "-profile", "live",
            "-frag-rap",
            "-fps", str(self.options.framerate),
            "-timescale", str(self.timescale),
            "-rap",
            "-out", "manifest",
            str(moov_filename),
        ]
        logging.debug('MP4Box arguments: %s', args)
        cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            subprocess.check_call(args)
        finally:
            os.chdir(cwd)
        moov = Path(prefix + "init.mp4")
        if self.options.verbose:
            subprocess.call(["ls", tmpdir])
        self.create_file_from_fragments(dest_filename, moov, prefix)

    def parse_representation(self, filename: str) -> Representation:
        parser = mp4.IsoParser()
        logging.debug('Parse %s', filename)
        atoms = parser.walk_atoms(filename)
        verbose = 2 if self.options.verbose else 0
        logging.debug('Create Representation from "%s"', filename)
        return Representation.load(filename=filename.replace('\\', '/'),
                                   atoms=atoms, verbose=verbose)

    def probe_media_info(self):
        info = json.loads(subprocess.check_output([
            "ffprobe",
            "-v", "0",
            "-of", "json",
            "-show_format",
            "-show_streams",
            self.options.source
        ]))
        if self.options.aspect is None:
            self.options.aspect = '1'
            self.options.aspect_ratio = 1.0
            for s in info["streams"]:
                try:
                    if s["codec_type"] != "video":
                        continue
                except KeyError:
                    continue
                try:
                    self.options.set_aspect(s["display_aspect_ratio"])
                except KeyError:
                    width = s["width"]
                    height = s["height"]
                    m = self.gcd(width, height)
                    width /= m
                    height /= m
                    self.options.aspect = f'{width}:{height}'
                    self.options.aspect_ratio = width / height
        if self.options.duration == 0:
            self.options.duration = math.floor(float(info["format"]["duration"]))
        # round duration to be a multiple of fragment duration
        self.options.duration = int(
            (self.options.duration // self.options.segment_duration) *
            self.options.segment_duration)
        if self.options.framerate == 0:
            for s in info["streams"]:
                try:
                    fps = s["avg_frame_rate"]
                    if '/' in fps:
                        n, d = fps.split('/')
                        if float(d) == 0:
                            continue
                        fps = int(round(float(n) / float(d)))
                    else:
                        fps = int(fps)
                    self.options.framerate = fps
                    break
                except KeyError:
                    pass
        assert self.options.framerate > 0
        assert self.options.segment_duration > 0

        # Duration of a segment (in frames)
        self.frame_segment_duration = math.floor(
            self.options.segment_duration * self.options.framerate)
        assert self.frame_segment_duration > 0

        # The MP4 timescale to use for video
        self.timescale = self.options.framerate * 10

        return info

    @staticmethod
    def gcd(x, y):
        while y:
            x, y = (y, x % y)
        return x

    @classmethod
    def main(cls, args: list[str]) -> int:
        ap = argparse.ArgumentParser(description='DASH encoding and packaging')
        ap.add_argument('--duration', '-d', help='Stream duration (in seconds) (0=auto)',
                        type=int, default=0)
        ap.add_argument('--aspect', help='Aspect ratio (default=same as source)')
        ap.add_argument('--avc3', help='Use in-band (AVC3 format) init segments',
                        action="store_true")
        ap.add_argument('--surround', help='Add E-AC3 surround-sound audio track',
                        action="store_true")
        ap.add_argument('--font', help='Truetype font file to use to show bitrate', type=str,
                        dest='font', default=None)
        ap.add_argument('--frag', help='Fragment duration (in seconds)', type=float,
                        dest='segment_duration', default=4)
        ap.add_argument('--fps', help='Frames per second (0=auto)', type=int,
                        dest='framerate', default=0)
        ap.add_argument('--input', '-i', help='Input audio/video file', required=True,
                        dest='source')
        ap.add_argument('--kid', help='Key ID ("random" = auto generate KID)', nargs="*")
        ap.add_argument('--key', help='Encryption Key', nargs="*")
        ap.add_argument('-v', '--verbose', help='Verbose mode', action="store_true")
        ap.add_argument('--output', '-o', help='Output directory', dest='output', required=True)
        ap.add_argument('--prefix', '-p', help='Prefix for output files', required=True)
        args = ap.parse_args(args)

        logging.basicConfig()
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s: %(message)s'))
        mp4_log = logging.getLogger('mp4')
        mp4_log.addHandler(ch)
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
            mp4_log.setLevel(logging.DEBUG)

        dmc = cls(MediaCreateOptions(**vars(args)))
        dmc.probe_media_info()
        dmc.encode_all()
        dmc.package_all()
        if args.kid:
            dmc.encrypt_all()
        mi = dmc.options.destdir / f'{args.prefix}.json'
        dmc.media_info['streams'][0]['files'].sort()
        with mi.open('wt', encoding='utf-8') as f:
            json.dump(dmc.media_info, f, indent=2)
        return 0


if __name__ == "__main__":
    sys.exit(DashMediaCreator.main(sys.argv[1:]))
