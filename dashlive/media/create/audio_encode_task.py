import logging
from pathlib import Path
import subprocess
from typing import Sequence

from .creation_result import CreationResult
from .encoding_parameters import AudioEncodingParameters
from .ffmpeg_helper import AudioStreamInfo
from .media_create_options import MediaCreateOptions
from .task import MediaCreationTask

class AudioEncodingTask(MediaCreationTask):
    params: AudioEncodingParameters
    file_index: int
    track_id: int
    source: Path
    dest_dir: Path
    dest_file: Path
    info: AudioStreamInfo

    def __init__(self, options: MediaCreateOptions, source: Path, file_index: int,
                 track_id: int, params: AudioEncodingParameters, info: AudioStreamInfo) -> None:
        super().__init__(options)
        self.source = source
        self.params = params
        self.file_index = file_index
        self.track_id = track_id
        self.dest_dir = self.options.destdir / 'audio'
        self.dest_file = self.dest_dir / self.destination_filename('audio', self.file_index, False)
        self.info = info

    def __str__(self) -> str:
        return f"AudioEncodeTask: {self.source} -> {self.dest_file} track={self.track_id} params={self.params}"

    def run(self) -> Sequence[CreationResult]:
        if not self.source.exists():
            raise IOError(f"{self.source} not found")
        tmp_file: Path = self.dest_dir / f'{self.options.prefix}-a{self.file_index}-{self.params.codecString}.mp4'
        result: CreationResult = CreationResult(
            filename=self.dest_file, content_type='audio', current_track_id=self.track_id,
            final_track_id=self.track_id, duration=self.options.duration)
        if not self.dest_file.exists():
            self.dest_dir.mkdir(parents=True, exist_ok=True)
            self.encode_audio(tmp_file)
            if not tmp_file.exists():
                raise IOError(f"{tmp_file} not found")
            self.copy_and_modify(src_file=tmp_file, dest_file=self.dest_file, track_id=result.final_track_id,
                                 language=self.options.language)
        return [result]

    def encode_audio(self, dest_file: Path) -> None:
        ffmpeg_args: list[str] = [
            "ffmpeg",
            "-i", f"{self.source.absolute()}",
            "-map", "0:a:0",
            "-codec:a:0", self.params.codecString,
            "-b:a:0", f"{self.params.bitrate}k",
            "-ac:a:0", f"{self.params.channels}",
            "-y",
            "-t", str(self.options.duration),
        ]
        if self.params.codecString == 'aac':
            ffmpeg_args += ["-strict", "-2"]
        if self.params.channels != 2:
            ffmpeg_args += ["-af", f"channelmap=channel_layout={self.params.layout}"]
        ffmpeg_args.append(str(dest_file))
        logging.debug(ffmpeg_args)
        subprocess.check_call(ffmpeg_args)
