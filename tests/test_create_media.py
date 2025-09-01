import json
from pathlib import Path
import logging
import re
import shutil
import subprocess
from typing import ClassVar, Pattern
import unittest
from unittest.mock import patch

from pyfakefs.fake_filesystem_unittest import TestCase
from pyfakefs.fake_filesystem import FakeFilesystem

from dashlive.media.create import DashMediaCreator, FfmpegMediaInfo
from dashlive.media.create.encoding_parameters import BITRATE_PROFILES, VideoEncodingParameters
from dashlive.media.create.media_create_options import MediaCreateOptions
from dashlive.mpeg.dash.representation import Representation

from .mixins.mixin import TestCaseMixin

class DashMediaCreatorWithoutParser(TestCaseMixin, DashMediaCreator):
    def parse_representation(self, filename: str) -> Representation:
        name = Path(filename).stem
        prefix, num = name.split('_')
        self.assertIn(num[0], {'a', 'v'})
        num = num[1:]
        return Representation(track_id=int(num))


class MockFfmpeg(TestCaseMixin):
    options: MediaCreateOptions
    bitrate_index: int
    input_file: Path
    tmpdir: Path
    aspect: float
    fs: FakeFilesystem
    drive: str

    def __init__(self,
                 fs: FakeFilesystem,
                 input_file: Path,
                 tmpdir: Path,
                 options: MediaCreateOptions
                 ) -> None:
        super().__init__()
        self.fs = fs
        self.bitrate_index = 0
        self.input_file = input_file
        self.tmpdir = tmpdir
        self.drive = tmpdir.drive
        self.aspect = 16.0 / 9.0
        self.options = options

    def bitrate_ladder(self) -> list[VideoEncodingParameters]:
        return BITRATE_PROFILES[self.options.bitrate_profile]

    def assertListEqual(self, a: list, b: list) -> None:
        for one, two in zip(a, b):
            self.assertEqual(one, two)
        self.assertEqual(len(a), len(b))

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
        return self.ffmpeg_video_encode(args)

    def which(self, cmd: str | Path, mode: int = 1, path: str | Path | None = None) -> str | None:
        if f"{cmd}" in {'ffmpeg', 'ffprobe', 'MP4Box'}:
            return f"{self.drive}/usr/local/bin/{cmd}"
        return None

    def ffmpeg_video_encode(self, args: list[str]) -> int:
        ladder: list[VideoEncodingParameters] = self.bitrate_ladder()
        assert self.bitrate_index < len(ladder)
        width, height, bitrate, codec = ladder[self.bitrate_index]
        height = 4 * (int(float(height) / self.aspect) // 4)
        minrate = (bitrate * 10) // 14
        self.assertEqual(args[0], 'ffmpeg')
        self.assertEqual(args[-1], str(self.tmpdir / f'{bitrate}' / 'bbb.mp4'))
        expected: dict[str, str | None] = {
            '-i': f'{self.input_file}',
            '-video_track_timescale': '240',
            '-codec:v': 'libx264',
            '-aspect': '16:9',
            '-maxrate': f'{bitrate}k',
            '-minrate': f'{minrate}k',
            '-s': f'{width}x{height}',
            '-g': '96',
            '-force_key_frames': '0,4,8,12,16,20,24,28,32,36,40,44,48,52,56,60',
            '-t': '60',
            '-r': '24',
        }

        if self.bitrate_index == 0:
            expected.update({
                '-codec:a:0': self.options.audio_codec,
                '-b:a:0': '96k',
                '-ac:a:0': '2',
                '-y': None,
            })
            if self.options.surround:
                expected.update({
                    '-codec:a:1': 'eac3',
                    '-b:a:1': '320k',
                    '-ac:a:1': '6',
                })
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
        filename: Path
        for idx, br in enumerate(ladder, start=1):
            filename = self.tmpdir / f'{br[2]}' / 'bbb.mp4'
            expected.append(f'{filename}#video:id=v{idx}')
        min_br: int = ladder[0][2]
        mp4_dir: Path = self.tmpdir / 'dash'
        filename = self.tmpdir / f'{min_br}' / 'bbb.mp4'
        expected.append(f'{filename}#trackID=2:role=main:id=a1')
        if self.options.surround:
            filename = self.tmpdir / f'{min_br}' / 'bbb.mp4'
            expected.append(f'{filename}#trackID=3:role=alternate:id=a2')
        if self.options.subtitles:
            filename = self.tmpdir / 'BigBuckBunny.ttml'
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
        expected: list[str] = [
            'ffprobe', '-v', '0', '-of', 'json',
            '-show_format',
            '-show_streams',
            f'{self.input_file}',
        ]
        self.assertListEqual(expected, args)
        self.assertIsNone(stderr)
        self.assertFalse(universal_newlines)
        result: FfmpegMediaInfo = {
            'streams': [{
                'codec_type': 'video',
                'display_aspect_ratio': '16:9',
                'avg_frame_rate': '24',
                'width': 1920,
                'height': 1080,
            }],
            'format': {
                'duration': 60.0
            }
        }
        return json.dumps(result)

    def ffprobe_check_frames(self, args: list[str], stderr: int | None,
                             universal_newlines: bool, text: bool) -> str:
        ladder: list[VideoEncodingParameters] = self.bitrate_ladder()
        assert self.bitrate_index < len(ladder)
        width, height, bitrate, codec = ladder[self.bitrate_index]
        expected: list[str] = [
            'ffprobe',
            '-show_frames',
            '-print_format', 'compact',
            str(self.tmpdir / f'{bitrate}' / 'bbb.mp4')
        ]
        self.assertEqual(expected, args)
        self.assertIsNotNone(stderr)
        self.assertTrue(text)
        self.bitrate_index += 1
        result: list[str] = []
        for num in range(60 * 24 * 10):
            pts = num * 100
            if num % (24 * 4) == 0:
                key_frame = '1'
            else:
                key_frame = '0'
            frame_info = [
                'frame',
                'media_type=video',
                'stream_index=0',
                f'key_frame={key_frame}',
                f'pts={pts}',
                f'coded_picture_number={num}'
            ]
            result.append('|'.join(frame_info))
        return '\r\n'.join(result)

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

    def run_creator_main(self, args: list[str], ffmpeg: MockFfmpeg) -> int:
        logging.disable(logging.CRITICAL)
        with patch.multiple(subprocess, check_call=ffmpeg.check_call,
                            check_output=ffmpeg.check_output):
            with patch.object(shutil, 'which', ffmpeg.which):
                with patch('dashlive.mpeg.mp4.Mp4Atom'):
                    rv: int = DashMediaCreatorWithoutParser.main(args)
        return rv

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
            '--surround',
            '-o', str(tmpdir)
        ]
        opts: MediaCreateOptions = MediaCreateOptions.parse_args(args)
        self.assertEqual(opts.audio_codec, 'aac')
        self.assertFalse(opts.subtitles)
        self.assertTrue(opts.surround)
        ffmpeg = MockFfmpeg(self.fs, src_file, tmpdir, opts)
        rv: int = self.run_creator_main(args, ffmpeg)
        self.assertEqual(rv, 0)
        js_file: Path = tmpdir / 'bbb.json'
        with js_file.open('rt') as src:
            js_data = json.load(src)
        files: list[str] = [
            'bbb_a1.mp4', 'bbb_a1_enc.mp4',
            'bbb_a2.mp4', 'bbb_a2_enc.mp4']

        ladder: list[VideoEncodingParameters] = ffmpeg.bitrate_ladder()
        for idx in range(1, len(ladder) + 1):
            files.append(f'bbb_v{idx}.mp4')
            files.append(f'bbb_v{idx}_enc.mp4')
        files.sort()
        expected = {
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
        self.assertFalse(opts.surround)
        ffmpeg = MockFfmpeg(self.fs, src_file, tmpdir, opts)
        rv: int = self.run_creator_main(args, ffmpeg)
        self.assertEqual(rv, 0)
        js_file: Path = tmpdir / 'bbb.json'
        with js_file.open('rt') as src:
            js_data = json.load(src)
        files: list[str] = ['bbb_a1.mp4']

        ladder: list[VideoEncodingParameters] = ffmpeg.bitrate_ladder()
        for idx in range(1, len(ladder) + 1):
            files.append(f'bbb_v{idx}.mp4')
        files.sort()
        expected = {
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
        self.assertEqual(opts.audio_codec, 'aac')
        self.assertTrue(opts.subtitles)
        self.assertFalse(opts.surround)
        ffmpeg = MockFfmpeg(self.fs, src_file, tmpdir, opts)
        rv: int = self.run_creator_main(args, ffmpeg)
        self.assertEqual(rv, 0)
        js_file: Path = tmpdir / 'bbb.json'
        with js_file.open('rt') as src:
            js_data = json.load(src)
        files: list[str] = ['bbb_a1.mp4', 'bbb_t1.mp4']
        ladder: list[VideoEncodingParameters] = ffmpeg.bitrate_ladder()
        for idx in range(1, len(ladder) + 1):
            files.append(f'bbb_v{idx}.mp4')
        files.sort()
        expected = {
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
        ffmpeg = MockFfmpeg(self.fs, src_file, tmpdir, opts)
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
