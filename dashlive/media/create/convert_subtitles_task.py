#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import json
import logging
from pathlib import Path
import subprocess
from typing import TypedDict

from ttconv.tt import main as ttconv_main

from .media_create_options import MediaCreateOptions
from .task import CreationResult, MediaCreationTask

class TtconvGeneralOptions(TypedDict):
    progress_bar: bool
    log_level: str
    document_lang: str

class TtconvLcdOptions(TypedDict):
    bg_color: str | None
    color: str | None

class TtconvMainOptions(TypedDict):
    general: TtconvGeneralOptions
    lcd: TtconvLcdOptions

class ConvertSubtitlesTask(MediaCreationTask):
    src: Path
    dest: Path
    track_id: int
    use_ttconv: bool

    def __init__(self, options: MediaCreateOptions, src: Path, dest: Path, track_id: int,
                 use_ttconv: bool = True) -> None:
        super().__init__(options)
        self.src = src
        self.dest = dest
        self.track_id = track_id
        self.use_ttconv = use_ttconv

    def __str__(self) -> str:
        return f"ConvertSubtitlesTask: {self.src} -> {self.dest} track={self.track_id}"

    def run(self) -> list[CreationResult]:
        if not self.src.exists():
            raise IOError(f"{self.src} not found")
        if not self.dest.exists():
            if self.use_ttconv:
                self.convert_subtitles_using_ttconv(self.src, self.dest)
            else:
                self.convert_subtitles_using_gpac(self.src, self.dest)
        result: CreationResult = CreationResult(
            filename=self.dest, content_type='text', current_track_id=1,
            final_track_id=self.track_id, duration=self.options.duration)
        return [result]

    @staticmethod
    def convert_subtitles_using_gpac(src: Path, ttml: Path) -> None:
        args: list[str] = [
            'gpac',
            '-i', f"{src.absolute()}",
            '-o', f"{ttml.absolute()}",
        ]
        subprocess.check_call(args)

    def convert_subtitles_using_ttconv(self, src: Path, ttml: Path) -> None:
        config: TtconvMainOptions = {
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
