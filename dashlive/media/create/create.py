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
import json
import logging
import os
import math
from pathlib import Path
import shutil
import subprocess
from typing import Protocol, Sequence, cast

from dashlive.drm.key_tuple import KeyTuple
from dashlive.drm.keymaterial import KeyMaterial
from dashlive.drm.playready import PlayReady
from dashlive.media.create.audio_encode_task import AudioEncodingTask
from dashlive.media.create.convert_subtitles_task import ConvertSubtitlesTask
from dashlive.media.create.encrypt_media_task import EncryptMediaTask
from dashlive.media.create.ffmpeg_types import FfmpegMediaInfo
from dashlive.media.create.media_create_options import MediaCreateOptions
from dashlive.media.create.media_info_json import KeyInfoJson, MediaInfoJson, StreamInfoJson
from dashlive.media.create.package_sources_task import PackageSourcesTask
from dashlive.media.create.task import CreationResult
from dashlive.media.create.video_encode_task import VideoEncodeTask

from .encoding_parameters import BITRATE_PROFILES, VideoEncodingParameters
from .encoded_representation import EncodedRepresentation

class RunnableTask(Protocol):
    def run(self) -> Sequence[CreationResult]:
        ...


class DashMediaCreator:
    options: MediaCreateOptions
    media_info: MediaInfoJson
    pending_tasks: list[RunnableTask]
    completed_tasks: list[RunnableTask]
    generated_files: list[CreationResult]
    keys: list[KeyTuple]

    def __init__(self, options: MediaCreateOptions) -> None:
        self.options = options
        self.pending_tasks = []
        self.completed_tasks = []
        self.media_info = {
            "keys": [],
            "streams": []
        }
        self.keys = self.create_all_media_keys()

    def create_all_tasks(self) -> None:
        self.pending_tasks = []
        self.completed_tasks = []
        self.generated_files = []
        ladder: list[VideoEncodingParameters] = BITRATE_PROFILES[self.options.bitrate_profile]
        for width, height, bitrate, codec in ladder:
            if self.options.max_bitrate > 0 and bitrate > self.options.max_bitrate:
                continue
            task = VideoEncodeTask(
                options=self.options, height=height, width=width, bitrate=bitrate,
                codec=codec)
            self.pending_tasks.append(task)

        self.pending_tasks.append(AudioEncodingTask(
            options=self.options, source=self.options.source, bitrate=96,
            codecString=self.options.audio_codec, channels=2, file_index=1))

        if self.options.surround:
            self.pending_tasks.append(AudioEncodingTask(
                options=self.options, source=self.options.source, bitrate=320,
                codecString='eac3', channels=6, file_index=2))

        if self.options.subtitles:
            src: Path = Path(self.options.subtitles)
            ttml_file: Path = self.options.destdir / src.with_suffix('.ttml').name
            self.pending_tasks.append(ConvertSubtitlesTask(
                options=self.options, src=src, dest=ttml_file))

        self.pending_tasks.append(PackageSourcesTask(self.options, self.get_unpackaged_media_files))

    def get_unpackaged_media_files(self) -> list[CreationResult]:
        media_files: list[CreationResult] = []
        for cf in self.generated_files:
            if not isinstance(cf, EncodedRepresentation):
                media_files.append(cf)
        return media_files

    def run_all_tasks(self) -> list[CreationResult]:
        if not self.options.source.exists():
            raise IOError(f'Input file "{self.options.source}" does not exist')
        done: bool = False
        while not done:
            try:
                task: RunnableTask = self.pending_tasks.pop(0)
                new_files: Sequence[CreationResult] = task.run()
                self.generated_files += new_files
                self.completed_tasks.append(task)
                self.add_encryption_tasks(new_files)
            except IndexError:
                done = True
        stream: StreamInfoJson = {
            "directory": self.options.prefix,
            "title": "",
            "files": []
        }
        for gf in self.generated_files:
            if not isinstance(gf, EncodedRepresentation):
                continue
            en_rep: EncodedRepresentation = cast(EncodedRepresentation, gf)
            stream["files"].append(en_rep.filename.name)
        stream["files"].sort()
        self.media_info["streams"] = [stream]
        return self.generated_files

    def add_encryption_tasks(self, new_files: Sequence[CreationResult]) -> None:
        if not self.keys:
            return
        for nf in new_files:
            if not isinstance(nf, EncodedRepresentation):
                continue
            if nf.content_type not in {'audio', 'video'}:
                continue
            en_rep: EncodedRepresentation = cast(EncodedRepresentation, nf)
            if en_rep.encrypted:
                continue
            key: KeyTuple = self.keys[min(en_rep.track_id, len(self.keys)) - 1]
            self.pending_tasks.append(EncryptMediaTask(options=self.options, key=key, src=en_rep))

    def create_all_media_keys(self) -> list[KeyTuple]:
        if not self.options.kid:
            return []
        kid_list: list[str] = self.create_key_ids()
        assert len(kid_list) > 0
        key_list: list[str | None] = [None] * len(kid_list)
        if self.options.key:
            key_list = [k for k in self.options.key]
        key_tuples: list[KeyTuple] = []
        for kid_str, key_str in zip(kid_list, key_list):
            kid_km = KeyMaterial(hex=kid_str)
            if key_str is None:
                key_km = KeyMaterial(raw=PlayReady.generate_content_key(kid_km.raw))
            else:
                key_km = KeyMaterial(hex=key_str)
            logging.debug('Using key %s for kid %s', key_km.hex, kid_km.hex)
            kt = KeyTuple(kid_km, key_km, ALG="AESCTR")
            key_tuples.append(kt)

        media_keys: dict[str, KeyInfoJson] = {}
        for kt in key_tuples:
            item: KeyInfoJson = {
                "kid": kt.KID.hex,
                "computed": not self.options.key
            }
            if not item['computed']:
                item["key"] = kt.KEY.hex
            media_keys[kt.KID.hex] = item
        self.media_info["keys"] = list(media_keys.values())
        self.media_info["keys"].sort(key=lambda item: item['kid'])

        return key_tuples

    def create_key_ids(self) -> list[str]:
        rv: list[str] = []
        for kid in self.options.kid:
            if kid == 'random':
                kid = str(binascii.b2a_hex(os.urandom(KeyMaterial.length)), 'ascii')
            rv.append(kid)
        return rv

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

    @staticmethod
    def gcd(x: int, y: int) -> int:
        while y:
            x, y = (y, x % y)
        return x

    @staticmethod
    def check_for_missing_tools() -> bool:
        missing_tools: bool = False
        for tool in ("ffmpeg", "ffprobe", "MP4Box"):
            if shutil.which(tool) is None:
                logging.error("Error: Required tool '%s' is not installed or not in PATH.", tool)
                missing_tools = True
        return missing_tools

    @staticmethod
    def main(argv: list[str]) -> int:
        logging.basicConfig()
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s: %(message)s'))
        mp4_log = logging.getLogger('mp4')
        mp4_log.addHandler(ch)

        if DashMediaCreator.check_for_missing_tools():
            return 1

        args: MediaCreateOptions = MediaCreateOptions.parse_args(argv)
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
            mp4_log.setLevel(logging.DEBUG)
        args.destdir.mkdir(exist_ok=True)
        dmc = DashMediaCreator(args)
        dmc.probe_media_info()
        dmc.create_all_tasks()
        dmc.run_all_tasks()
        mi: Path = dmc.options.destdir / f'{args.prefix}.json'
        dmc.media_info['streams'][0]['files'].sort()
        with mi.open('wt', encoding='utf-8') as f:
            json.dump(dmc.media_info, f, indent=2)
        return 0
