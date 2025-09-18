import json
from pathlib import Path
import logging
import re
import shutil
import subprocess
from typing import ClassVar, Pattern, cast
import unittest
from unittest.mock import patch

from pyfakefs.fake_filesystem_unittest import TestCase
from pyfakefs.fake_filesystem import FakeFilesystem

from dashlive.media.create import DashMediaCreator
from dashlive.media.create.encoding_parameters import BITRATE_PROFILES, VideoEncodingParameters
from dashlive.media.create.ffmpeg_helper import (
    AudioStreamInfo,
    FfmpegMediaJson,
    FfmpegStreamJson,
    MediaFormatInfo,
    MediaProbeResults,
    VideoFrameJson,
    VideoStreamInfo
)
from dashlive.media.create.media_create_options import MediaCreateOptions
from dashlive.media.create.media_info_json import MediaInfoJson
from dashlive.media.create.convert_subtitles_task import TtconvMainOptions
from dashlive.mpeg.dash.representation import Representation

from .mixins.mixin import TestCaseMixin

class DashMediaCreatorWithoutParser(TestCaseMixin, DashMediaCreator):
    def parse_representation(self, filename: str) -> Representation:
        name = Path(filename).stem
        prefix, num = name.split('_')
        self.assertIn(num[0], {'a', 'v'})
        num = num[1:]
        return Representation(track_id=int(num))


class MockMediaTools(TestCaseMixin):
    options: MediaCreateOptions
    input_file: Path
    tmpdir: Path
    aspect: float
    media_duration: float
    fs: FakeFilesystem
    drive: str

    def __init__(self,
                 fs: FakeFilesystem,
                 input_file: Path,
                 tmpdir: Path,
                 options: MediaCreateOptions,
                 media_duration: float = 60
                 ) -> None:
        super().__init__()
        self.fs = fs
        self.input_file = input_file
        self.tmpdir = tmpdir
        self.drive = tmpdir.drive
        self.aspect = 16.0 / 9.0
        self.options = options
        self.media_duration = media_duration
        if self.options.duration == 0:
            self.options.duration = int(round(self.media_duration))

    def bitrate_ladder(self) -> list[VideoEncodingParameters]:
        return BITRATE_PROFILES[self.options.bitrate_profile]

    def assertListEqual(self, a: list, b: list) -> None:
        for one, two in zip(a, b):
            self.assertEqual(one, two)
        self.assertEqual(len(a), len(b))

    def assertCommandArguments(self, expected: dict[str, str | None], args: list[str]) -> None:
        required: set[str] = set(expected.keys())
        for idx, arg in enumerate(args):
            if arg[0] != '-':
                continue
            try:
                val: str | None = expected[arg]
                if val is not None:
                    msg: str = f'Expected {arg} to have value "{val}" but found "{args[idx + 1]}"'
                    self.assertEqual(val, args[idx + 1], msg=msg)
                required.remove(arg)
            except KeyError:
                self.assertNotIn(arg, required)
        self.assertEqual(required, set())

    def check_output(self, args: list[str], stderr: int | None = None,
                     universal_newlines: bool = False, text: bool = False) -> str:
        if '-show_format' in ' '.join(args):
            return self.ffprobe_source_stream_info(args, stderr, universal_newlines, text)
        return self.ffprobe_check_frames(args, stderr, universal_newlines, text)

    def check_call(self, args: list[str], cwd: Path | str | None = None) -> int:
        if args[0] == 'MP4Box':
            if args[1] == '-crypt':
                return self.mp4box_encrypt(args)
            if 'moov-enc' in args[-1]:
                return self.mp4box_build_encrypted(args)
            return self.mp4box_build(args)
        if '-codec:v' in args:
            return self.ffmpeg_video_encode(args)
        return self.ffmpeg_audio_encode(args)

    def which(self, cmd: str | Path, mode: int = 1, path: str | Path | None = None) -> str | None:
        if f"{cmd}" in {'ffmpeg', 'ffprobe', 'MP4Box'}:
            return f"{self.drive}/usr/local/bin/{cmd}"
        return None

    def find_encoding_parameters(self, filename: str) -> VideoEncodingParameters:
        ladder: list[VideoEncodingParameters] = self.bitrate_ladder()
        dest_file: Path = Path(filename)
        for item in ladder:
            fname: Path = self.tmpdir / f'{item.bitrate}' / 'bbb.mp4'
            if fname == dest_file:
                return item
        raise IndexError(filename)

    def ffmpeg_video_encode(self, args: list[str]) -> int:
        params: VideoEncodingParameters = self.find_encoding_parameters(args[-1])
        height: int = 4 * (int(float(params.height) / self.aspect) // 4)
        minrate: int = (params.bitrate * 10) // 14
        self.assertEqual(args[0], 'ffmpeg')
        expected: dict[str, str | None] = {
            '-i': f'{self.input_file}',
            '-video_track_timescale': '240',
            '-codec:v': 'libx264',
            '-aspect': '16:9',
            '-maxrate': f'{params.bitrate}k',
            '-minrate': f'{minrate}k',
            '-s': f'{params.width}x{height}',
            '-g': '96',
            '-force_key_frames': '0,4,8,12,16,20,24,28,32,36,40,44,48,52,56,60',
            '-t': f"{self.options.duration}",
            '-r': '24',
        }
        self.assertCommandArguments(expected, args)
        self.fs.create_file(args[-1], contents=args[-1])
        return 0

    def ffmpeg_audio_encode(self, args: list[str]) -> int:
        expected: dict[str, str | None] = {
            '-i': f'{self.input_file}',
            '-codec:a:0': self.options.audio_codec,
            '-b:a:0': '96k',
            '-ac:a:0': '2',
            '-y': None,
        }
        try:
            chan_idx: int = args.index('-ac:a:0')
            if args[chan_idx + 1] == '6':
                expected.update({
                    '-codec:a:0': 'eac3',
                    '-ac:a:0': '6',
                    '-b:a:0': '320k',
                })
        except ValueError:
            pass
        self.assertCommandArguments(expected, args)
        self.fs.create_file(args[-1], contents=args[-1])
        return 0

    def mp4box_build(self, args: list[str]) -> int:
        expected: list[str] = [
            'MP4Box',
            '-dash', '960',
            '-frag', '960',
            '-dash-scale', '240',
            '-rap',
            '-fps', '24',
            '-frag-rap',
            '-profile', 'live',
            '-profile-ext', 'urn:dvb:dash:profile:dvb-dash:2014',
            '-bs-switching', 'merge',
            '-lang', 'eng',
            '-segment-ext', 'mp4',
            '-segment-name', 'dash_$RepresentationID$_$Number%03d$$Init=init$',
            '-out', 'manifest',
        ]
        ladder: list[VideoEncodingParameters] = self.bitrate_ladder()
        dur: int = 60
        if self.options.duration > 0:
            dur = self.options.duration
        filename: Path
        for idx, br in enumerate(ladder, start=1):
            filename = self.tmpdir / f'{br[2]}' / 'bbb.mp4'
            self.assertTrue(filename.exists())
            expected.append(f'{filename}#trackID=1:id=v{idx}:dur={dur}')
        track_id: int = 2
        mp4_dir: Path = self.tmpdir / 'dash'
        filename = self.tmpdir / 'audio' / 'bbb_a1.mp4'
        self.assertTrue(filename.exists())
        expected.append(f'{filename}#trackID={track_id}:role=main:id=a1:dur={dur}')
        track_id += 1
        for idx in range(2, 2 + len(self.options.audio_sources)):
            filename = self.tmpdir / 'audio' / f'bbb_a{idx}.mp4'
            self.assertTrue(filename.exists())
            expected.append(f'{filename}#trackID={track_id}:role=alternate:id=a{idx}:dur={dur}')
            track_id += 1
        if self.options.subtitles is not None:
            filename = self.tmpdir / 'BigBuckBunny.ttml'
            self.assertTrue(filename.exists())
            expected.append(f'{filename}#trackID=1:role=main:id=t1:dur=94.0:ddur=8')
            self.fs.create_file(mp4_dir / 'BigBuckBunny.ttml', contents='BigBuckBunny.ttml')
        self.maxDiff = None
        self.assertListEqual(expected, args)

        for rep_id in range(1, 3 + len(ladder)):
            self.make_fake_mp4_file(mp4_dir / f'dash_{rep_id}_init.mp4')
            for segment in range(1, 6):
                self.make_fake_mp4_file(mp4_dir / f'dash_{rep_id}_{segment:03d}.mp4')

        return 0

    def mp4box_encrypt(self, args: list[str]) -> int:
        expected: list[str | Pattern] = [
            'MP4Box',
            '-crypt', re.compile(r'drm.xml$'),
            '-out', re.compile(r'-moov-enc.mp4$'),
        ]
        if args[-1].startswith('bbb_v'):
            expected += ['-fps', '24']

        expected.append(re.compile(r'(bbb_[av]\d+).mp4$'))
        self.assertRegexListEqual(expected, args)
        for idx, arg in enumerate(args):
            if arg == '-out':
                self.fs.create_file(args[idx + 1], contents=args[idx + 1])
        return 0

    def mp4box_build_encrypted(self, args: list[str]) -> int:
        expected: list[str | Pattern] = [
            'MP4Box',
            '-dash', '960',
            '-frag', '960',
            '-segment-ext', 'mp4',
            '-segment-name', 'dash_enc_$Number%03d$$Init=init$',
            '-profile', 'live',
            '-frag-rap',
            '-fps', '24',
            '-timescale', '240',
            '-rap',
            '-out', 'manifest',
            re.compile(r'-moov-enc.mp4$'),
        ]
        self.assertRegexListEqual(expected, args)
        enc_tmp: Path = Path(args[-1]).parent
        self.make_fake_mp4_file(enc_tmp / 'dash_enc_init.mp4')
        for segment in range(1, 6):
            self.make_fake_mp4_file(enc_tmp / f'dash_enc_{segment:03d}.mp4')
        return 0

    def make_fake_mp4_file(self, filename: Path) -> None:
        self.fs.create_file(filename, contents=f"{filename}")

    def ffprobe_source_stream_info(self, args: list[str], stderr: int | None,
                                   universal_newlines: bool, text: bool) -> str:
        src_file = Path(args[-1])
        if not src_file.exists():
            raise IOError(f'File {src_file} does not exist')
        expected: list[str] = [
            'ffprobe', '-v', '0', '-of', 'json',
            '-show_format',
            '-show_streams',
            args[-1],
        ]
        self.assertListEqual(expected, args)
        self.assertIsNone(stderr)
        self.assertFalse(universal_newlines)
        result: FfmpegMediaJson = {
            'streams': [{
                "index": 0,
                "codec_name": "h264",
                "profile": "High",
                'codec_type': 'video',
                'display_aspect_ratio': '16:9',
                'avg_frame_rate': '24',
                'width': 1920,
                'height': 1080,
                "duration": f"{self.media_duration}",
            }, {
                "index": 1,
                "codec_name": "aac",
                "profile": "LC",
                "codec_type": "audio",
                "sample_rate": "44100",
                "channels": 2,
                "channel_layout": "stereo",
                "avg_frame_rate": "0/0",
                "duration": f"{self.media_duration - 0.01}",
            }],
            'format': {
                "filename": args[-1],
                "nb_streams": 2,
                "nb_programs": 0,
                "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                "start_time": "0.000000",
                "duration": f"{self.media_duration}",
                "size": "738876331",
                "bit_rate": "8051319",
            }
        }
        if src_file != self.input_file:
            result['format']['nb_streams'] = 1
            result['streams'] = [result['streams'][1]]
            result['streams'][0].update({
                "index": 0,
                "codec_name": src_file.suffix[1:],
                "channels": 6,
                "channel_layout": "5.1(side)",
            })
        result['format']['format_name'] = src_file.suffix[1:]
        return json.dumps(result)

    def ffprobe_check_frames(self, args: list[str], stderr: int | None,
                             universal_newlines: bool, text: bool) -> str:
        self.find_encoding_parameters(args[-1])
        expected: list[str] = [
            "ffprobe",
            "-v", "0",
            "-show_frames",
            "-print_format", "json",
            args[-1],
        ]
        self.assertEqual(expected, args)
        self.assertIsNotNone(stderr)
        self.assertTrue(text)
        frames: list[VideoFrameJson] = []
        frame_types: list[str] = ['P', 'B', 'B', 'B']
        for num in range(60 * 24 * 10):
            pts: int = num * 100
            if num % (24 * 4) == 0:
                key_frame: int = 1
            else:
                key_frame = 0
            vid: VideoFrameJson = {
                'key_frame': key_frame,
                'pts': pts,
                'duration': 100,
                'pkt_pos': f"{num}",
                'pkt_size': "123",
                'pict_type': frame_types[num % len(frame_types)],
                'interlaced_frame': 0,
                'top_field_first': 1,
            }
            if key_frame:
                vid['pict_type'] = 'I'
            frames.append(vid)
        return json.dumps(dict(frames=frames))

    def ttconv_main(self, args: list[str]) -> None:
        self.assertIsNotNone(self.options.subtitles)
        ttml: Path = self.options.destdir / cast(Path, self.options.subtitles).with_suffix(".ttml").name
        expected: dict[str, str | None] = {
            "-i": f"{self.options.subtitles}",
            "-o": f"{ttml.absolute()}",
            "--otype": "TTML",
            "--filter": "lcd",
        }
        self.assertCommandArguments(expected, args)
        for idx, arg in enumerate(args):
            if arg == "--config":
                config: TtconvMainOptions = json.loads(args[idx + 1])
                self.assertEqual(config["general"]["document_lang"], self.options.language)
        self.fs.create_file(ttml, contents=f"{ttml}")

    def assertRegexListEqual(self, expected: list[str | Pattern[str]],
                             actual: list[str]) -> None:
        self.assertEqual(len(expected), len(actual))
        index = 0
        for exp, act in zip(expected, actual):
            msg: str = f'item[{index}]: expected "{exp}" got "{act}"'
            if isinstance(exp, str):
                self.assertEqual(exp, act, msg=msg)
            else:
                match: re.Match[str] | None = exp.search(act)
                self.assertIsNotNone(match, msg)

class TestMediaCreation(TestCase):
    SRC_DIR: ClassVar[Path] = Path(__file__).parent.parent.parent.absolute()
    drive: str
    input_dir: Path

    def setUp(self) -> None:
        super().setUp()
        self.setUpPyfakefs()
        self.drive = TestMediaCreation.SRC_DIR.drive
        self.input_dir = Path(f'{self.drive}/input')
        self.fs.create_dir(self.input_dir)

    def tearDown(self) -> None:
        logging.disable(logging.NOTSET)

    def create_temp_folder(self) -> Path:
        drive: str = self.SRC_DIR.drive
        tmpdir: Path = Path(f'{drive}/tmp/TestMediaCreation')
        if not tmpdir.exists():
            self.fs.create_dir(tmpdir)
        return tmpdir

    def run_creator_main(self, args: list[str], mocks: MockMediaTools) -> int:
        logging.disable(logging.CRITICAL)
        with patch.multiple(subprocess, check_call=mocks.check_call,
                            check_output=mocks.check_output):
            with patch.object(shutil, 'which', mocks.which):
                with patch('dashlive.mpeg.mp4.Mp4Atom'):
                    with patch('dashlive.media.create.convert_subtitles_task.ttconv_main', new=mocks.ttconv_main):
                        rv: int = DashMediaCreatorWithoutParser.main(args)
        return rv

    def test_convert_media_probe_json(self) -> None:
        src_file: Path = self.input_dir / 'BigBuckBunny.mp4'
        input: FfmpegMediaJson = {
            'streams': [{
                "index": 0,
                "codec_name": "h264",
                "profile": "High",
                'codec_type': 'video',
                'display_aspect_ratio': '16:9',
                'avg_frame_rate': '24',
                'width': 1920,
                'height': 1080,
                "duration": "734.122086",
            }, {
                "index": 1,
                "codec_name": "aac",
                "profile": "LC",
                "codec_type": "audio",
                "sample_rate": "44100",
                "channels": 2,
                "channel_layout": "stereo",
                "avg_frame_rate": "0/0",
                "duration": "734.122086",
            }],
            'format': {
                "filename": f"{src_file}",
                "nb_streams": 2,
                "nb_programs": 0,
                "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                "start_time": "0.000000",
                "duration": "734.166667",
                "size": "738876331",
                "bit_rate": "8051319",
            }
        }
        expected_format: MediaFormatInfo = MediaFormatInfo(
            duration=734.166667,
            format_name="mov,mp4,m4a,3gp,3g2,mj2",
            start_time=0,
            size=738876331,
            bit_rate=8051319
        )
        vid = VideoStreamInfo(
            content_type='video',
            index=0,
            codec="h264",
            duration=734.122086,
            profile="High",
            display_aspect_ratio="16:9",
            width=1920,
            height=1080,
            framerate=24)
        aud = AudioStreamInfo(
            content_type='audio',
            index=1,
            codec="aac",
            duration=734.122086,
            profile="LC",
            sample_rate=44100,
            channels=2,
            channel_layout="stereo")

        info: MediaProbeResults = MediaProbeResults.from_json(input)
        self.maxDiff = None
        self.assertEqual(info.format, expected_format)
        self.assertEqual(len(info.video), 1)
        self.assertEqual(len(info.audio), 1)
        self.assertEqual(info.video[0], vid)
        self.assertEqual(info.audio[0], aud)

    def test_convert_ac3_audio_probe(self) -> None:
        input: FfmpegStreamJson = {
            "index": 1,
            "codec_name": "ac3",
            "codec_type": "audio",
            "sample_rate": "48000",
            "channels": 6,
            "channel_layout": "5.1(side)",
            "duration": "734.016000",
        }
        info: AudioStreamInfo = AudioStreamInfo.from_json(input)
        expected: AudioStreamInfo = AudioStreamInfo(
            content_type='audio',
            index=1,
            codec="eac3",
            duration=734.016,
            profile=None,
            sample_rate=48000,
            channels=6,
            channel_layout="5.1")
        self.maxDiff = None
        self.assertEqual(expected, info)

    def test_encode_with_surround_audio(self) -> None:
        tmpdir: Path = self.create_temp_folder()
        kid = '1ab45440532c439994dc5c5ad9584bac'
        src_file: Path = self.input_dir / 'BigBuckBunny.mp4'
        self.fs.create_file(src_file, contents=f"{src_file}")
        args: list[str] = [
            '-i', f"{src_file}",
            '-p', 'bbb',
            '--font', f'{self.SRC_DIR.drive}/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
            '--kid', kid,
            '--channels', '6',
            '--acodec', 'ac3',
            '-o', str(tmpdir)
        ]
        opts: MediaCreateOptions = MediaCreateOptions.parse_args(args)
        self.assertEqual(opts.audio_codec, 'eac3')
        self.assertFalse(opts.subtitles)
        ffmpeg = MockMediaTools(self.fs, src_file, tmpdir, opts)
        rv: int = self.run_creator_main(args, ffmpeg)
        self.assertEqual(rv, 0)
        js_file: Path = tmpdir / 'bbb.json'
        with js_file.open('rt') as src:
            js_data: MediaInfoJson = json.load(src)
        files: list[str] = ['bbb_a1.mp4', 'bbb_a1_enc.mp4']
        ladder: list[VideoEncodingParameters] = ffmpeg.bitrate_ladder()
        for idx in range(1, len(ladder) + 1):
            files.append(f'bbb_v{idx}.mp4')
            files.append(f'bbb_v{idx}_enc.mp4')
        files.sort()
        expected: MediaInfoJson = {
            'keys': [{
                'kid': kid,
                'computed': True
            }],
            'streams': [{
                'directory': 'bbb',
                'title': '',
                'files': files
            }]
        }
        self.maxDiff = None
        self.assertDictEqual(expected, js_data)

    def test_encode_with_multiple_audio_tracks(self) -> None:
        tmpdir: Path = self.create_temp_folder()
        kid = '1ab45440532c439994dc5c5ad9584bac'
        src_file: Path = self.input_dir / 'BigBuckBunny.mp4'
        self.fs.create_file(src_file, contents=f"{src_file}")
        audio_src: Path = self.input_dir / 'ExtraAudio.wav'
        self.fs.create_file(audio_src, contents=f"{audio_src}")
        args: list[str] = [
            '-i', f"{src_file}",
            '--audio', f"{audio_src}",
            '-p', 'bbb',
            '--kid', kid,
            '-o', str(tmpdir)
        ]
        opts: MediaCreateOptions = MediaCreateOptions.parse_args(args)
        self.assertIsNone(opts.audio_codec)
        self.assertFalse(opts.subtitles)
        ffmpeg = MockMediaTools(self.fs, src_file, tmpdir, opts)
        rv: int = self.run_creator_main(args, ffmpeg)
        self.assertEqual(rv, 0)
        js_file: Path = tmpdir / 'bbb.json'
        with js_file.open('rt') as src:
            js_data: MediaInfoJson = json.load(src)
        files: list[str] = [
            'bbb_a1.mp4', 'bbb_a1_enc.mp4',
            'bbb_a2.mp4', 'bbb_a2_enc.mp4']

        ladder: list[VideoEncodingParameters] = ffmpeg.bitrate_ladder()
        for idx in range(1, len(ladder) + 1):
            files.append(f'bbb_v{idx}.mp4')
            files.append(f'bbb_v{idx}_enc.mp4')
        files.sort()
        expected: MediaInfoJson = {
            'keys': [{
                'kid': kid,
                'computed': True
            }],
            'streams': [{
                'directory': 'bbb',
                'title': '',
                'files': files
            }]
        }
        self.maxDiff = None
        self.assertDictEqual(expected, js_data)

    def test_encode_with_eac3_audio(self) -> None:
        tmpdir: Path = self.create_temp_folder()
        src_file: Path = self.input_dir / 'BigBuckBunny.mp4'
        self.fs.create_file(src_file, contents=f"{src_file}")
        args: list[str] = [
            '-i', f"{src_file}",
            '-p', 'bbb',
            '--acodec', 'eac3',
            '-o', str(tmpdir)
        ]
        opts: MediaCreateOptions = MediaCreateOptions.parse_args(args)
        self.assertEqual(opts.audio_codec, 'eac3')
        self.assertFalse(opts.subtitles)
        ffmpeg = MockMediaTools(self.fs, src_file, tmpdir, opts)
        rv: int = self.run_creator_main(args, ffmpeg)
        self.assertEqual(rv, 0)
        js_file: Path = tmpdir / 'bbb.json'
        with js_file.open('rt') as src:
            js_data: MediaInfoJson = json.load(src)
        files: list[str] = ['bbb_a1.mp4']

        ladder: list[VideoEncodingParameters] = ffmpeg.bitrate_ladder()
        for idx in range(1, len(ladder) + 1):
            files.append(f'bbb_v{idx}.mp4')
        files.sort()
        expected: MediaInfoJson = {
            'keys': [],
            'streams': [{
                'directory': 'bbb',
                'title': '',
                'files': files
            }]
        }
        self.assertDictEqual(expected, js_data)

    def test_encode_with_subtitles(self) -> None:
        subtitles: Path = self.input_dir / 'BigBuckBunny.srt'
        lines: list[str] = [
            "1",
            "00:00:23,000 --> 00:00:24,500",
            "You're a jerk, Thom.",
            "",
            "2",
            "00:00:25,000 --> 00:00:26,999",
            "Look Celia, we have to follow our passions;",
            "",
        ]
        with subtitles.open('wt') as dest:
            for line in lines:
                dest.write(f"{line}\n")

        tmpdir: Path = self.create_temp_folder()
        src_file: Path = self.input_dir / 'BigBuckBunny.mp4'
        self.fs.create_file(src_file, contents=f"{src_file}")
        args: list[str] = [
            '-i', f"{src_file}",
            '-p', 'bbb',
            '--subtitles', f'{subtitles}',
            '-o', str(tmpdir)
        ]
        opts: MediaCreateOptions = MediaCreateOptions.parse_args(args)
        self.assertIsNone(opts.audio_codec)
        self.assertTrue(opts.subtitles)
        ffmpeg = MockMediaTools(self.fs, src_file, tmpdir, opts)
        rv: int = self.run_creator_main(args, ffmpeg)
        self.assertEqual(rv, 0)
        js_file: Path = tmpdir / 'bbb.json'
        with js_file.open('rt') as src:
            js_data: MediaInfoJson = json.load(src)
        files: list[str] = ['bbb_a1.mp4', 'bbb_t1.mp4']
        ladder: list[VideoEncodingParameters] = ffmpeg.bitrate_ladder()
        for idx in range(1, len(ladder) + 1):
            files.append(f'bbb_v{idx}.mp4')
        files.sort()
        expected: MediaInfoJson = {
            'keys': [],
            'streams': [{
                'directory': 'bbb',
                'title': '',
                'files': files
            }]
        }
        self.maxDiff = None
        self.assertDictEqual(expected, js_data)

    def test_missing_input_file(self) -> None:
        src_file: Path = self.input_dir / 'BigBuckBunny.mp4'
        tmpdir: Path = self.create_temp_folder()
        args: list[str] = [
            '-i', f"{src_file}",
            '-p', 'bbb',
            '-o', str(tmpdir)
        ]
        opts: MediaCreateOptions = MediaCreateOptions.parse_args(args)
        ffmpeg = MockMediaTools(self.fs, src_file, tmpdir, opts)
        with self.assertRaises(IOError):
            self.run_creator_main(args, ffmpeg)

    def test_missing_media_tool(self) -> None:
        src_file: Path = self.input_dir / 'BigBuckBunny.mp4'
        self.fs.create_file(src_file, contents=f"{src_file}")
        tmpdir: Path = self.create_temp_folder()
        args: list[str] = [
            '-i', f"{src_file}",
            '-p', 'bbb',
            '-o', str(tmpdir)
        ]
        logging.disable(logging.CRITICAL)
        for tool in ['ffmpeg', 'ffprobe', 'MP4Box']:
            def mock_which(cmd: str) -> str | None:
                if cmd == tool:
                    return None
                return f'/usr/bin/{cmd}'

            with patch.object(shutil, 'which', mock_which):
                with patch('dashlive.mpeg.mp4.Mp4Atom'):
                    rv: int = DashMediaCreatorWithoutParser.main(args)
                    self.assertEqual(rv, 1)


if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    unittest.main()
