import ctypes
import json
from pathlib import Path
import logging
import multiprocessing
import shutil
import subprocess
from typing import Optional
import tempfile
import unittest
from unittest.mock import patch

from dashlive.testcase.mixin import TestCaseMixin
from dashlive.media.create import DashMediaCreator
from dashlive.mpeg.dash.representation import Representation

class DashMediaCreatorWithoutParser(DashMediaCreator, TestCaseMixin):
    def parse_representation(self, filename: str) -> Representation:
        name = Path(filename).stem
        prefix, num = name.split('_')
        self.assertIn(num[0], {'a', 'v'})
        num = num[1:]
        return Representation(track_id=int(num))


class MockFfmpeg(TestCaseMixin):
    def __init__(self, tmpdir: Path) -> None:
        self.stage: int = 0
        self.tmpdir = tmpdir
        self.aspect = 16.0 / 9.0

    def check_output(self, args, stderr=None, universal_newlines=False) -> str:
        self.assertEqual(self.stage % 2, 0)
        if self.stage == 0:
            rv = self.ffprobe_source_stream_info(args, stderr, universal_newlines)
        else:
            rv = self.ffprobe_check_frames(args, stderr, universal_newlines)
        self.stage += 1
        return rv

    def check_call(self, args: list[str]) -> int:
        if self.stage < 15:
            self.assertEqual(self.stage % 2, 1)
            rv = self.ffmpeg_video_encode(args)
        elif self.stage == 15:
            rv = self.mp4box_build(args)
        else:
            phase = (self.stage - 16) % 2
            if phase == 0:
                rv = self.mp4box_encrypt(args)
            else:
                rv = self.mp4box_build_encrypted(args)
        self.stage += 1
        return rv

    def mkdtemp(self) -> str:
        rv = self.tmpdir / f'{self.stage}'
        rv.mkdir()
        return str(rv)

    def ffmpeg_video_encode(self, args: list[str]) -> int:
        width, height, bitrate = DashMediaCreator.BITRATE_LADDER[(self.stage - 1) // 2]
        height = 4 * (int(float(height) / self.aspect) // 4)
        minrate = (bitrate * 10) // 14
        assert args[0] == 'ffmpeg'
        assert args[-1] == str(self.tmpdir / f'{bitrate}' / 'bbb.mp4')
        expected = {
            '-i': 'BigBuckBunny.mp4',
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
            '-codec:a:0': 'aac',
            '-b:a:0': '96k',
            '-ac:a:0': '2',
            '-codec:a:1': 'eac3',
            '-b:a:1': '320k',
            '-ac:a:1': '6',
        }
        for idx, arg in enumerate(args):
            if arg[0] == '-':
                try:
                    val = expected[arg]
                    msg = f'Expected {arg} to have value "{val}" but found "{args[idx + 1]}"'
                    self.assertEqual(val, args[idx + 1], msg=msg)
                except KeyError:
                    pass
        return 0

    def mp4box_build(self, args: list[str]) -> int:
        expected = [
            'MP4Box',
            '-dash', '960',
            '-frag', '960',
            '-dash-scale', '240',
            '-rap',
            '-fps', '24',
            '-frag-rap',
            '-profile', 'live',
            '-profile-ext', 'urn:dvb:dash:profile:dvbdash:2014',
            '-bs-switching', 'merge',
            '-segment-ext', 'mp4',
            '-segment-name', 'dash_$RepresentationID$_$number%03d$$Init=init$',
            '-out', 'manifest',
        ]
        for br in DashMediaCreator.BITRATE_LADDER:
            expected.append(str(self.tmpdir / f'{br[2]}' / 'bbb.mp4#video'))
        min_br = DashMediaCreator.BITRATE_LADDER[0][2]
        expected.append(str(self.tmpdir / f'{min_br}' / 'bbb.mp4#trackID=2:role=main'))
        expected.append(str(self.tmpdir / f'{min_br}' / 'bbb.mp4#trackID=3:role=alternate'))
        self.assertListEqual(expected, args)
        mp4_dir = self.tmpdir / 'dash'
        for rep_id in range(1, 3 + len(DashMediaCreator.BITRATE_LADDER)):
            self.make_fake_mp4_file(mp4_dir / f'dash_{rep_id}_init.mp4')
            for segment in range(1, 6):
                self.make_fake_mp4_file(mp4_dir / f'dash_{rep_id}_{segment:03d}.mp4')
        return 0

    def mp4_prefix(self) -> str:
        rep_id = 1 + ((self.stage - 16) // 2)
        av = 'v'
        if rep_id > len(DashMediaCreator.BITRATE_LADDER):
            av = 'a'
            rep_id -= len(DashMediaCreator.BITRATE_LADDER)
        return f'bbb_{av}{rep_id}'

    def mp4box_encrypt(self, args: list[str]) -> int:
        prefix = self.mp4_prefix()
        enc_tmp = self.tmpdir / f'{self.stage}'
        expected = [
            'MP4Box',
            '-crypt', str(enc_tmp / 'drm.xml'),
            '-out', str(enc_tmp / f'{prefix}-moov-enc.mp4'),
            '-fps', '24',
            str(self.tmpdir / f'{prefix}.mp4')
        ]
        self.assertListEqual(expected, args)
        return 0

    def mp4box_build_encrypted(self, args: list[str]) -> int:
        enc_tmp = self.tmpdir / f'{self.stage - 1}'
        prefix = self.mp4_prefix()
        expected = [
            'MP4Box',
            '-dash', '960',
            '-frag', '960',
            '-segment-ext', 'mp4',
            '-segment-name', 'dash_enc_$number%03d$$Init=init$',
            '-profile', 'live',
            '-frag-rap',
            '-fps', '24',
            '-timescale', '240',
            '-rap',
            '-out', 'manifest',
            str(enc_tmp / f'{prefix}-moov-enc.mp4')
        ]
        self.assertListEqual(expected, args)
        self.make_fake_mp4_file(enc_tmp / 'dash_enc_init.mp4')
        for segment in range(1, 6):
            self.make_fake_mp4_file(enc_tmp / f'dash_enc_{segment:03d}.mp4')
        return 0

    def make_fake_mp4_file(self, filename: Path) -> None:
        with filename.open('wb') as dest:
            dest.write(bytes(str(filename), 'utf-8'))

    def ffprobe_source_stream_info(self, args: list[str], stderr: Optional[int],
                                   universal_newlines: bool) -> str:
        expected = [
            'ffprobe', '-v', '0', '-of', 'json',
            '-show_format', '-show_streams', 'BigBuckBunny.mp4'
        ]
        self.assertListEqual(expected, args)
        self.assertIsNone(stderr)
        self.assertFalse(universal_newlines)
        result = {
            'streams': [{
                'codec_type': 'video',
                'display_aspect_ratio': '16:9',
                'avg_frame_rate': '24',
            }],
            'format': {
                'duration': 60.0
            }
        }
        return json.dumps(result)

    def ffprobe_check_frames(self, args, stderr, universal_newlines) -> str:
        width, height, bitrate = DashMediaCreator.BITRATE_LADDER[(self.stage - 2) // 2]
        expected = [
            'ffprobe',
            '-show_frames',
            '-print_format', 'compact',
            str(self.tmpdir / f'{bitrate}' / 'bbb.mp4')
        ]
        self.assertEqual(expected, args)
        self.assertIsNotNone(stderr)
        self.assertTrue(universal_newlines)
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

class TestMediaCreation(unittest.TestCase):
    _temp_dir = multiprocessing.Array(ctypes.c_char, 1024)

    def tearDown(self):
        if self._temp_dir.value:
            shutil.rmtree(self._temp_dir.value, ignore_errors=True)
        logging.disable(logging.NOTSET)

    def create_temp_folder(self) -> Path:
        tmpdir = tempfile.mkdtemp()
        self._temp_dir.value = bytes(tmpdir, 'utf-8')
        return Path(tmpdir)

    def test_encode(self, stage: int = 0) -> None:
        tmpdir = self.create_temp_folder()
        kid = '1ab45440532c439994dc5c5ad9584bac'
        args = [
            '-i', "BigBuckBunny.mp4",
            '-p', 'bbb',
            '--font', '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
            '--kid', kid,
            '-o', str(tmpdir)
        ]
        ffmpeg = MockFfmpeg(tmpdir)
        logging.disable(logging.CRITICAL)
        with patch.object(subprocess, 'check_call', ffmpeg.check_call):
            with patch.object(subprocess, 'check_output', ffmpeg.check_output):
                with patch.object(tempfile, 'mkdtemp', ffmpeg.mkdtemp):
                    rv = DashMediaCreatorWithoutParser.main(args)
        self.assertEqual(rv, 0)
        js_file = tmpdir / 'bbb.json'
        with js_file.open('rt') as src:
            js_data = json.load(src)
        files = [
            'bbb_a1.mp4', 'bbb_a1_enc.mp4',
            'bbb_a2.mp4', 'bbb_a2_enc.mp4']
        for idx in range(1, 8):
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


if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    unittest.main()
