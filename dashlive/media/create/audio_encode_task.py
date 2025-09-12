import logging
from pathlib import Path
import subprocess
from typing import Sequence

from .creation_result import CreationResult
from .encoding_parameters import AudioEncodingParameters
from .media_create_options import MediaCreateOptions
from .task import MediaCreationTask

class AudioEncodingTask(MediaCreationTask):
    params: AudioEncodingParameters
    file_index: int
    source: Path

    def __init__(self, options: MediaCreateOptions, source: Path, file_index: int, params: AudioEncodingParameters) -> None:
        super().__init__(options)
        self.source = source
        self.params = params
        self.file_index = file_index

    def run(self) -> Sequence[CreationResult]:
        dest_dir: Path = self.options.destdir / 'audio'
        tmp_file: Path = dest_dir / f'{self.options.prefix}-a{self.file_index}-{self.params.codecString}.mp4'
        dest_file: Path = dest_dir / self.destination_filename('audio', self.file_index, False)
        result: CreationResult = CreationResult(
            filename=dest_file, content_type='audio', track_id=self.file_index + 1,
            duration=self.options.duration)
        if not dest_file.exists():
            dest_dir.mkdir(parents=True, exist_ok=True)
            self.encode_audio(tmp_file)
            assert tmp_file.exists()
            self.copy_and_modify(src_file=tmp_file, dest_file=dest_file, track_id=result.track_id,
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

        ffmpeg_args.append(str(dest_file))
        logging.debug(ffmpeg_args)
        subprocess.check_call(ffmpeg_args)
