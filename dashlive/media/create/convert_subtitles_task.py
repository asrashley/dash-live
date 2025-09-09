import json
import logging
from pathlib import Path
import subprocess
from typing import Any

from ttconv.tt import main as ttconv_main

from .media_create_options import MediaCreateOptions
from .task import MediaCreationTask

class ConvertSubtitlesTask(MediaCreationTask):
    src: Path
    dest: Path
    use_ttconv: bool

    def __init__(self, options: MediaCreateOptions, src: Path, dest: Path, use_ttconv: bool = True) -> None:
        super().__init__(options)
        self.src = src
        self.dest = dest
        self.use_ttconv = use_ttconv

    def run(self) -> None:
        if self.use_ttconv:
            self.convert_subtitles_using_ttconv(self.src, self.dest)
        else:
            self.convert_subtitles_using_gpac(self.src, self.dest)

    @staticmethod
    def convert_subtitles_using_gpac(src: Path, ttml: Path) -> None:
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


