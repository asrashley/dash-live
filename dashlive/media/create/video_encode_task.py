#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import logging
from pathlib import Path
import subprocess
from typing import Sequence, cast
from dashlive.media.create.encoding_parameters import AudioEncodingParameters
from dashlive.media.create.media_create_options import MediaCreateOptions
from dashlive.media.create.task import CreationResult, MediaCreationTask
from dashlive.mpeg.codec_strings import CodecData, H264Codec, H265Codec, codec_data_from_string

class VideoEncodeTask(MediaCreationTask):
    width: int
    height: int
    bitrate: int
    codec: str | None
    audio: bool
    timescale: int
    audio_tracks: list[AudioEncodingParameters] = []

    def __init__(self, options: MediaCreateOptions, width: int, height: int,
                 bitrate: int, codec: str | None, audio: bool) -> None:
        super().__init__(options)
        self.width = width
        self.height = height
        self.bitrate = bitrate
        self.codec = codec
        self.audio = audio

    def run(self) -> Sequence[CreationResult]:
        """
        Encode the stream and check key frames are in the correct place
        """
        destdir: Path = self.options.destdir / f'{self.bitrate}'
        dest: Path = destdir / f'{self.options.prefix}.mp4'
        result: CreationResult = CreationResult(
            filename=dest, content_type='video', track_id=1, duration=self.options.duration)
        if dest.exists():
            return [result]
        destdir.mkdir(parents=True, exist_ok=True)
        height: int = 4 * (int(float(self.height) / self.options.aspect_ratio) // 4)
        logging.debug("%s: %dx%d %d Kbps", dest, self.width, height, self.bitrate)
        cbr: int = (self.bitrate * 10) // 12
        minrate: int = (self.bitrate * 10) // 14
        vcodec: str = "libx264"
        # buffer_size is set to 75% of VBV limit
        buffer_size = 4000
        level: float = 0
        tier: int = 0
        if self.codec is None:
            profile = "baseline"
            level = 3.1
            if height > 720:
                profile = "high"
                level = 4.0
                # buffer_size is set to 75% of VBV limit
                buffer_size = 25000
            elif self.width > 640:
                profile = "main"
        else:
            codec_data: CodecData = codec_data_from_string(self.codec)
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
            "-video_track_timescale", f"{self.options.timescale}",
            "-map", "0:v:0",
        ]

        if self.options.font is not None:
            drawtext: str = ':'.join([
                'fontfile=' + self.options.font,
                'fontsize=48',
                f'text={self.bitrate} Kbps',
                'x=(w-tw)/2',
                'y=h-(2*lh)',
                'fontcolor=white',
                'box=1',
                'boxcolor=0x000000@0.7'])
            ffmpeg_args.append("-vf")
            ffmpeg_args.append(f"drawtext={drawtext}")

        if self.audio:
            ffmpeg_args += ["-map", "0:a:0"]
            if self.options.surround:
                ffmpeg_args += ["-map", "0:a:0"]

        ffmpeg_args += [
            "-codec:v", vcodec,
            "-aspect", self.options.aspect,
            "-profile:v", profile,
            "-field_order", "progressive",
            "-maxrate", f'{self.bitrate:d}k',
            "-minrate", f'{minrate:d}k',
        ]

        if level > 0:
            ffmpeg_args += ["-level:v", str(level)]

        if vcodec == "libx264":
            ffmpeg_args += [
                "-bufsize", f'{buffer_size:d}k',
                "-x264opts", f"keyint={self.options.frame_segment_duration:d}:videoformat=pal",
            ]
        elif vcodec == 'libx265':
            x265_params: list[str] = [
                f"keyint={self.options.frame_segment_duration:d}",
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
            "-s", f"{self.width:d}x{height:d}",
            "-flags", "+cgop+global_header",
            "-flags2", "-local_header",
            "-g", str(self.options.frame_segment_duration),
            "-sc_threshold", "0",
            "-force_key_frames", ','.join(keyframes),
            "-y",
            "-t", str(self.options.duration),
            "-threads", "0",
        ]

        if self.options.framerate:
            ffmpeg_args += ["-r", str(self.options.framerate)]

        if self.audio:
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

        self.check_key_frames(dest)

        return [result]

    def check_key_frames(self, dest: Path) -> None:
        logging.info('Checking key frames in %s', dest)
        ffmpeg_args: list[str] = [
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
                    frame_segment_duration: int = self.options.frame_segment_duration
                    assert frame_segment_duration is not None
                    assert frame_segment_duration > 0
                    if (idx % frame_segment_duration) == 0 and info['key_frame'] != '1':
                        logging.warning('Info: %s', info)
                        raise ValueError(f'Frame {idx} should be a key frame')
                    idx += 1
            except KeyError:
                pass
