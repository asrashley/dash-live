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

import binascii
import datetime
import io
import json
import logging
import os
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, BinaryIO, ClassVar, cast

from ttconv.tt import main as ttconv_main

from dashlive.drm.keymaterial import KeyMaterial
from dashlive.drm.playready import PlayReady
from dashlive.media.create.ffmpeg_types import FfmpegMediaInfo
from dashlive.media.create.media_create_options import MediaCreateOptions
from dashlive.mpeg import mp4
from dashlive.mpeg.codec_strings import CodecData, H264Codec, H265Codec, codec_data_from_string
from dashlive.mpeg.dash.representation import Representation
from dashlive.utils.timezone import UTC

from .encoding_parameters import BITRATE_PROFILES, AudioEncodingParameters, VideoEncodingParameters
from .encoded_representation import EncodedRepresentation

class InitialisationVector(KeyMaterial):
    length: ClassVar[int] = 8


class DashMediaCreator:
    # See https://wiki.gpac.io/xmlformats/Common-Encryption
    XML_TEMPLATE: ClassVar[str] = """<?xml version="1.0" encoding="UTF-8"?>
    <GPACDRM type="CENC AES-CTR">
      <CrypTrack trackID="{track_id:d}" IsEncrypted="1" IV_size="{iv_size:d}"
        first_IV="{iv}" saiSavedBox="senc">
        <key KID="0x{kid}" value="0x{key}" />
      </CrypTrack>
    </GPACDRM>
    """

    options: MediaCreateOptions
    timescale: int | None
    frame_segment_duration: int | None
    media_info: dict[str, list]
    audio_tracks: list[AudioEncodingParameters]

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
        self.audio_tracks = [
            AudioEncodingParameters(
                bitrate=96, codecString=self.options.audio_codec, channels=2)
        ]
        if self.options.surround:
            self.audio_tracks.append(AudioEncodingParameters(
                bitrate=320, codecString='eac3', channels=6))

    def encode_all(self) -> None:
        if not self.options.source.exists():
            raise IOError(f'Input file "{self.options.source}" does not exist')
        first: bool = True
        ladder: list[VideoEncodingParameters] = BITRATE_PROFILES[self.options.bitrate_profile]
        for width, height, bitrate, codec in ladder:
            if self.options.max_bitrate > 0 and bitrate > self.options.max_bitrate:
                continue
            self.encode_representation(width, height, bitrate, codec, first)
            first = False

        if self.options.subtitles:
            src: Path = Path(self.options.subtitles)
            ttml_file: Path = self.options.destdir / src.with_suffix('.ttml').name
            if not ttml_file.exists():
                self.convert_subtitles(src, ttml_file)

    def encode_representation(self, width: int, height: int,
                              bitrate: int, codec: str | None,
                              audio: bool) -> None:
        """
        Encode the stream and check key frames are in the correct place
        """
        destdir: Path = self.options.destdir / f'{bitrate}'
        dest: Path = destdir / f'{self.options.prefix}.mp4'
        if dest.exists():
            return
        destdir.mkdir(parents=True, exist_ok=True)
        height = 4 * (int(float(height) / self.options.aspect_ratio) // 4)
        logging.debug("%s: %dx%d %d Kbps", dest, width, height, bitrate)
        cbr: int = (bitrate * 10) // 12
        minrate: int = (bitrate * 10) // 14
        vcodec: str = "libx264"
        # buffer_size is set to 75% of VBV limit
        buffer_size = 4000
        level: float = 0
        tier: int = 0
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
            codec_data: CodecData = codec_data_from_string(codec)
            profile: str = codec_data.profile_string()
            if codec_data.codec == 'h.264':
                level = cast(H264Codec, codec_data).level
                if level >= 4.0:
                    buffer_size = 25000
            elif codec_data.codec == 'h.265':
                vcodec = 'libx265'
                profile = profile.split('.')[0]
                hevc: H265Codec = cast(H265Codec, codec_data)
                level = hevc.profile_idc * 10 + hevc.profile_compatibility_flags
                tier = hevc.tier_flag
        keyframes: list[str] = []
        pos: float = 0
        end: float = self.options.duration + self.options.segment_duration
        while pos < end:
            keyframes.append(f'{pos}')
            pos += self.options.segment_duration

        ffmpeg_args: list[str] = [
            "ffmpeg",
            "-ec", "deblock",
            "-i", f"{self.options.source.absolute()}",
            "-video_track_timescale", str(self.timescale),
            "-map", "0:v:0",
        ]

        if self.options.font is not None:
            drawtext: str = ':'.join([
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

        if audio:
            ffmpeg_args += ["-map", "0:a:0"]
            if self.options.surround:
                ffmpeg_args += ["-map", "0:a:0"]

        ffmpeg_args += [
            "-codec:v", vcodec,
            "-aspect", self.options.aspect,
            "-profile:v", profile,
            "-field_order", "progressive",
            "-maxrate", f'{bitrate:d}k',
            "-minrate", f'{minrate:d}k',
        ]

        if level > 0:
            ffmpeg_args += ["-level:v", str(level)]

        if vcodec == "libx264":
            ffmpeg_args += [
                "-bufsize", f'{buffer_size:d}k',
                "-x264opts", f"keyint={self.frame_segment_duration:d}:videoformat=pal",
            ]
        elif vcodec == 'libx265':
            x265_params: list[str] = [
                f"keyint={self.frame_segment_duration:d}",
                "level-idc={level}",
            ]
            if tier > 0:
                x265_params.append("high-tier")
            ffmpeg_args += [
                "-x265-params", ":".join(x265_params),
            ]

        ffmpeg_args += [
            "-b:v", f"{cbr:d}k",
            "-pix_fmt", "yuv420p",
            "-s", f"{width:d}x{height:d}",
            "-flags", "+cgop+global_header",
            "-flags2", "-local_header",
            "-g", str(self.frame_segment_duration),
            "-sc_threshold", "0",
            "-force_key_frames", ','.join(keyframes),
            "-y",
            "-t", str(self.options.duration),
            "-threads", "0",
        ]

        if self.options.framerate:
            ffmpeg_args += ["-r", str(self.options.framerate)]

        if audio:
            for idx, trk in enumerate(self.audio_tracks):
                ffmpeg_args += [
                    f"-codec:a:{idx}", trk.codecString,
                    f"-b:a:{idx}", f"{trk.bitrate}k",
                    f"-ac:a:{idx}", f"{trk.channels}",
                ]
                if trk.codecString == 'aac':
                    ffmpeg_args += ["-strict", "-2"]

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
        probe: str = subprocess.check_output(
            ffmpeg_args, stderr=subprocess.STDOUT, text=True)
        for line in probe.splitlines():
            info: dict[str, str] = {}
            if '|' not in line:
                continue
            for i in line.split('|'):
                if '=' not in i:
                    continue
                k, v = i.split('=')
                info[k] = v
            try:
                if info['media_type'] == 'video':
                    assert self.frame_segment_duration is not None
                    if (idx % self.frame_segment_duration) == 0 and info['key_frame'] != '1':
                        logging.warning('Info: %s', info)
                        raise ValueError(f'Frame {idx} should be a key frame')
                    idx += 1
            except KeyError:
                pass

    def create_file_from_fragments(self, dest_filename: Path, moov: Path, prefix: str) -> None:
        """
        Move all of the fragments into one file that starts with the init fragment.
        """
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
                moof: str = f'{prefix}{segment:03d}.mp4'
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

    def convert_subtitles(self, src: Path, ttml: Path) -> None:
        self.convert_subtitles_using_ttconv(src, ttml)

    def convert_subtitles_using_gpac(self, src: Path, ttml: Path) -> None:
        args: list[str] = [
            'gpac',
            '-i', f"{src.absolute()}",
            '-o', f"{ttml.absolute()}",
        ]
        subprocess.check_call(args)

    def convert_subtitles_using_ttconv(self, src: Path, ttml: Path) -> None:
        config: dict[str, Any] = {
            "general": {
                "progress_bar": False,
                "log_level": "WARN",
                "document_lang": self.options.language,
            },
            "lcd": {
                "bg_color": None,
                "color": None,
            },
        }
        argv: list[str] = [
            "convert",
            "-i", f"{src.absolute()}",
            "-o", f"{ttml.absolute()}",
            "--otype", "TTML",
            "--filter", "lcd",
            "--config", json.dumps(config),
        ]
        logging.debug('ttconv args: %s', argv)
        ttconv_main(argv)

    def package_all(self) -> bool:
        ladder: list[VideoEncodingParameters] = BITRATE_PROFILES[self.options.bitrate_profile]
        bitrates: list[int] = []
        for br in ladder:
            rate: int = br[2]
            if self.options.max_bitrate == 0 or rate <= self.options.max_bitrate:
                bitrates.append(rate)

        if self.nothing_to_do(bitrates):
            return False

        source_files: list[EncodedRepresentation] = []
        src_file: Path
        for index, bitrate in enumerate(bitrates, start=1):
            src_file = self.options.destdir / f'{bitrate}' / f'{self.options.prefix}.mp4'
            source_files.append(EncodedRepresentation(
                source=src_file, content_type='v', file_index=index, dest_track_id=1,
                rep_id=f"v{index}"))

        # Add AAC audio track
        src_file = self.options.destdir / f'{bitrates[0]}' / f'{self.options.prefix}.mp4'
        source_files.append(EncodedRepresentation(
            source=src_file, content_type='a', dest_track_id=2, file_index=1, role="main",
            src_track_id=2, rep_id="a1"))

        if self.options.surround:
            # Add E-AC3 audio track
            source_files.append(EncodedRepresentation(
                source=src_file, content_type='a', dest_track_id=3, file_index=2,
                src_track_id=3, role="alternate", rep_id="a2"))

        if self.options.subtitles:
            src_file = Path(self.options.subtitles)
            if src_file.suffix != ".ttml":
                src_file = self.options.destdir / src_file.with_suffix('.ttml').name
            # ! ugly hack !
            # for some reason, when a duration is provided to MP4Box, it only
            # produces a stream with 2/3 of the request duration
            source_files.append(EncodedRepresentation(
                source=src_file, content_type='t', src_track_id=1, dest_track_id=3,
                file_index=1, role="main", rep_id="t1",
                duration=self.options.duration * 1.5 + self.options.segment_duration,
                segment_duration=self.options.segment_duration * 2))

        self.package_sources(source_files)
        return True

    def nothing_to_do(self, bitrates: list[int]) -> bool:
        nothing_to_do: bool = True
        dest_file: Path
        for idx in range(len(bitrates)):
            dest_file = self.options.destdir / self.destination_filename('v', idx + 1, False)
            nothing_to_do = nothing_to_do and dest_file.exists()

        dest_file = self.options.destdir / self.destination_filename('a', 1, False)
        nothing_to_do = nothing_to_do and dest_file.exists()

        if self.options.surround:
            dest_file = self.options.destdir / self.destination_filename('a', 2, False)
            nothing_to_do = nothing_to_do and dest_file.exists()

        if self.options.subtitles:
            src: Path = Path(self.options.subtitles)
            ttml_file: Path = src
            if src.suffix != '.ttml':
                ttml_file = self.options.destdir / Path(self.options.subtitles).with_suffix('.ttml').name
            nothing_to_do = nothing_to_do and ttml_file.exists()
            dest_file = self.options.destdir / self.destination_filename('t', 1, False)
            nothing_to_do = nothing_to_do and dest_file.exists()

        return nothing_to_do

    def package_sources(self, source_files: list[EncodedRepresentation]) -> None:
        tmpdir: Path = self.options.destdir / "dash"
        tmpdir.mkdir(parents=True, exist_ok=True)
        bs_switching = 'inband' if self.options.avc3 else 'merge'
        assert self.timescale is not None
        mp4box_args: list[str] = [
            "MP4Box",
            "-dash", str(self.options.segment_duration * self.timescale),
            "-frag", str(self.options.segment_duration * self.timescale),
            "-dash-scale", str(self.timescale),
            "-rap",
            "-fps", str(self.options.framerate),
            "-frag-rap",
            "-profile", "live",
            "-profile-ext", "urn:dvb:dash:profile:dvb-dash:2014",
            "-bs-switching", bs_switching,
            "-lang", self.options.language,
            "-segment-ext", "mp4",
            "-segment-name", 'dash_$RepresentationID$_$Number%03d$$Init=init$',
            "-out", "manifest",
        ]
        for src in source_files:
            mp4box_args.append(src.mp4box_name())

        logging.debug('mp4box_args: %s', mp4box_args)
        cwd: str = os.getcwd()
        os.chdir(tmpdir)
        subprocess.check_call(mp4box_args)
        os.chdir(cwd)
        if self.options.verbose:
            subprocess.call(["ls", "-lR", tmpdir])

        for source in source_files:
            prefix = str(tmpdir / f'dash_{source.rep_id}_')
            dest_name: str = self.destination_filename(source.content_type, source.file_index, False)
            self.media_info['streams'][0]['files'].append(dest_name)
            dest_file: Path = self.options.destdir / dest_name
            if dest_file.exists():
                logging.debug('File %s exists, skipping generation', dest_file)
                continue
            moov: Path = tmpdir / f'dash_{source.rep_id}_init.mp4'
            logging.debug('try init filename: %s', moov)
            if not moov.exists():
                moov = tmpdir / 'dash_1_init.mp4'
                logging.debug('try init filename: %s', moov)
            if not moov.exists():
                moov = tmpdir / 'manifest_set1_init.mp4'
                logging.debug('try init filename: %s', moov)
            if not moov.exists():
                moov = Path(prefix + 'init.mp4')
                logging.debug('try init filename: %s', moov)
            if not moov.exists():
                logging.error('Failed to find init segment for representation %s: %s',
                              source.rep_id, prefix)
                continue
            logging.debug('Check for file: "%s"', dest_file)
            self.create_file_from_fragments(dest_file, moov, prefix)
            if source.src_track_id is not None and source.src_track_id != source.dest_track_id:
                self.modify_mp4_file(dest_file, source.dest_track_id, self.options.language)

    def destination_filename(self, contentType: str, index: int, encrypted: bool) -> str:
        enc: str = '_enc' if encrypted else ''
        return f'{self.options.prefix}_{contentType}{index:d}{enc}.mp4'

    def create_key_ids(self) -> list[str]:
        rv: list[str] = []
        for kid in self.options.kid:
            if kid == 'random':
                kid = str(binascii.b2a_hex(os.urandom(KeyMaterial.length)), 'ascii')
            rv.append(kid)
        return rv

    def encrypt_all(self) -> None:
        kids: list[str] = self.create_key_ids()
        assert len(kids) > 0
        kid_map: dict[str, KeyMaterial] = {
            'v': KeyMaterial(hex=kids[0]),
            'a': KeyMaterial(hex=kids[-1])
        }
        key_map: dict[str, KeyMaterial] = {}
        if self.options.key:
            assert isinstance(self.options.key, list)
            key_map = {
                'v': KeyMaterial(hex=self.options.key[0]),
                'a': KeyMaterial(hex=self.options.key[-1]),
            }
        else:
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

        ladder: list[VideoEncodingParameters] = BITRATE_PROFILES[self.options.bitrate_profile]
        files: list[tuple[str, int]] = []
        for idx in range(len(ladder)):
            files.append(('v', idx + 1))
        files.append(('a', 1))
        if self.options.surround:
            files.append(('a', 2))
        for contentType, index in files:
            src_file = self.options.destdir / self.destination_filename(contentType, index, False)
            dest_file = self.destination_filename(contentType, index, True)
            self.media_info['streams'][0]['files'].append(dest_file)
            iv = InitialisationVector(raw=os.urandom(self.options.iv_size // 8))
            self.encrypt_representation(
                src_file, self.options.destdir / dest_file, kid_map[contentType],
                key_map[contentType], iv)

    def encrypt_representation(
            self, source: Path, destfile: Path,
            kid: KeyMaterial, key: KeyMaterial, iv: InitialisationVector) -> None:
        if destfile.exists():
            logging.debug('File "%s" already exists, nothing to do', destfile)
            return
        with tempfile.TemporaryDirectory() as tmpdir:
            self.build_encrypted_file(source, destfile, kid, key, iv, Path(tmpdir))

    def build_encrypted_file(
            self, source: Path, dest_filename: Path,
            kid: KeyMaterial, key: KeyMaterial, iv: InitialisationVector,
            tmpdir: Path) -> None:
        assert source.exists()
        representation: Representation = self.parse_representation(str(source))
        basename: str = source.stem
        moov_filename: Path = tmpdir / f'{basename}-moov-enc.mp4'
        xmlfile: Path = tmpdir / "drm.xml"
        with xmlfile.open('wt', encoding='utf-8') as xml:
            template: str = self.XML_TEMPLATE.format(
                kid=kid.hex, key=key.hex, iv=iv.hex, iv_size=iv.length,
                track_id=representation.track_id)
            logging.debug("%s", template)
            xml.write(template)
        # MP4Box does not appear to be able to encrypt and fragment in one
        # stage, so first encrypt the media and then fragment it afterwards
        args: list[str] = [
            "MP4Box",
            "-crypt", str(xmlfile),
            "-out", str(moov_filename),
        ]
        if representation.content_type == 'video' and self.options.framerate:
            args += ["-fps", str(self.options.framerate)]
        args.append(str(source))
        logging.debug('MP4Box arguments: %s', args)
        subprocess.check_call(args, cwd=self.options.destdir)

        assert moov_filename.exists()

        prefix = str(tmpdir / "dash_enc_")
        assert self.timescale is not None
        args = [
            "MP4Box",
            "-dash", str(self.options.segment_duration * self.timescale),
            "-frag", str(self.options.segment_duration * self.timescale),
            "-segment-ext", "mp4",
            "-segment-name", 'dash_enc_$Number%03d$$Init=init$',
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
        atoms: list[mp4.Mp4Atom] = cast(list[mp4.Mp4Atom], parser.walk_atoms(filename))
        verbose: int = 2 if self.options.verbose else 0
        logging.debug('Create Representation from "%s"', filename)
        return Representation.load(filename=filename.replace('\\', '/'),
                                   atoms=atoms, verbose=verbose)

    def probe_media_info(self) -> None:
        info: FfmpegMediaInfo = json.loads(subprocess.check_output([
            "ffprobe",
            "-v", "0",
            "-of", "json",
            "-show_format",
            "-show_streams",
            f"{self.options.source.absolute()}",
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
        self.frame_segment_duration = int(math.floor(
            self.options.segment_duration * self.options.framerate))
        assert self.frame_segment_duration > 0

        # The MP4 timescale to use for video
        self.timescale = self.options.framerate * 10

    def modify_mp4_file(self, mp4file: Path, track_id: int, language: str,
                        encrypted: bool = False) -> None:
        """
        Updates the track ID and language tag of the specified MP4 file
        """
        mp4_options = mp4.Options(mode='rw', lazy_load=True)
        if encrypted:
            mp4_options.iv_size = self.options.iv_size

        logging.info('Modifying MP4 file "%s"', mp4file.name)
        with tempfile.TemporaryFile() as tmp:
            with mp4file.open('rb') as src:
                reader: io.BufferedReader = io.BufferedReader(src)
                atoms: list[mp4.Mp4Atom] = cast(list[mp4.Mp4Atom], mp4.Mp4Atom.load(
                    reader, options=mp4_options, use_wrapper=False))
                self.copy_and_modify(atoms, tmp, track_id, language)
            mp4file.unlink()
            tmp.seek(0)
            with mp4file.open('wb') as dest:
                shutil.copyfileobj(tmp, dest)

    @staticmethod
    def copy_and_modify(atoms: list[mp4.Mp4Atom], dest: BinaryIO, track_id: int, language: str) -> None:
        def modify_atom(atom: mp4.Mp4Atom) -> None:
            if atom.atom_type not in {'moov', 'moof'}:
                return
            if atom.atom_type == 'moov':
                moov: mp4.MovieBox = cast(mp4.MovieBox, atom)
                modified: bool = False
                if moov.trak.tkhd.track_id != track_id:
                    moov.trak.tkhd.track_id = track_id
                    moov.mvex.trex.track_id = track_id
                    moov.mvhd.next_track_id = track_id + 1
                    modified = True
                if moov.trak.mdia.mdhd.language != language:
                    moov.trak.mdia.mdhd.language = language
                    modified = True
                if modified:
                    moov.trak.tkhd.modification_time = datetime.datetime.now(tz=UTC())
                return
            moof: mp4.MovieFragmentBox = cast(mp4.MovieFragmentBox, atom)
            if moof.traf.tfhd.track_id != track_id:
                moof.traf.tfhd.track_id = track_id

        for atom in atoms:
            modify_atom(atom)
            atom.encode(dest)

    @staticmethod
    def gcd(x: int, y: int) -> int:
        while y:
            x, y = (y, x % y)
        return x

    @staticmethod
    def main(argv: list[str]) -> int:
        logging.basicConfig()
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s: %(message)s'))
        mp4_log = logging.getLogger('mp4')
        mp4_log.addHandler(ch)
        args: MediaCreateOptions = MediaCreateOptions.parse_args(argv)
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
            mp4_log.setLevel(logging.DEBUG)
        args.destdir.mkdir(exist_ok=True)
        dmc = DashMediaCreator(args)
        dmc.probe_media_info()
        dmc.encode_all()
        dmc.package_all()
        if args.kid:
            dmc.encrypt_all()
        mi: Path = dmc.options.destdir / f'{args.prefix}.json'
        dmc.media_info['streams'][0]['files'].sort()
        with mi.open('wt', encoding='utf-8') as f:
            json.dump(dmc.media_info, f, indent=2)
        return 0
