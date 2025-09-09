#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import argparse
from dataclasses import dataclass, field, InitVar
import math
from pathlib import Path
from typing import Any

from dashlive.media.create.encoding_parameters import BitrateProfiles


@dataclass
class MediaCreateOptions:
    aspect: str | None
    audio_codec: str
    avc3: bool
    bitrate_profile: BitrateProfiles
    duration: int
    font: str
    framerate: int
    kid: list[str]
    key: list[str]
    segment_duration: float
    surround: bool
    verbose: bool
    max_bitrate: int
    prefix: str
    source: Path
    subtitles: str
    output: InitVar[str]
    language: str = "eng"
    iv_size: int = 64
    aspect_ratio: float = field(init=False)
    destdir: Path = field(init=False)

    def __post_init__(self, output: str) -> None:
        self.destdir = Path(output).absolute()
        if self.aspect is not None:
            self.set_aspect(self.aspect)

    @property
    def frame_segment_duration(self) -> int:
        """
        Duration of a segment (in frames)
        """
        return int(math.floor(self.segment_duration * self.framerate))

    @property
    def timescale(self) -> int:
        return int(math.ceil(self.framerate * 10))

    def set_profile(self, profile: str | BitrateProfiles) -> None:
        if isinstance(profile, str):
            self.bitrate_profile = BitrateProfiles.from_string(profile)
        else:
            self.bitrate_profile = profile

    def set_aspect(self, aspect: str) -> None:
        self.aspect = aspect
        if ':' in aspect:
            n, d = aspect.split(':')
            self.aspect_ratio = float(n) / float(d)
        else:
            self.aspect_ratio = float(aspect)

    @staticmethod
    def parse_args(argv: list[str]) -> "MediaCreateOptions":
        ap = argparse.ArgumentParser(description='DASH encoding and packaging')
        ap.add_argument('--acodec', dest='audio_codec', default='aac',
                        help='Audio codec for main audio track')
        ap.add_argument('--duration', '-d',
                        help='Stream duration (in seconds) (0=auto)',
                        type=int, default=0)
        ap.add_argument('--aspect',
                        help='Aspect ratio (default=same as source)')
        ap.add_argument('--avc3',
                        help='Use in-band (AVC3 format) init segments',
                        action="store_true")
        ap.add_argument('--surround',
                        help='Add E-AC3 surround-sound audio track',
                        action="store_true")
        ap.add_argument('--subtitles',
                        help='Add subtitle text track')
        ap.add_argument('--font',
                        help='Truetype font file to use to show bitrate',
                        type=str, dest='font', default=None)
        ap.add_argument('--frag', help='Fragment duration (in seconds)',
                        type=float, dest='segment_duration', default=4)
        ap.add_argument('--fps', help='Frames per second (0=auto)', type=int,
                        dest='framerate', default=0)
        ap.add_argument('--max-bitrate',
                        help='Maximum bitrate (Kbps) (0=all bitrates)',
                        type=int, dest='max_bitrate', default=0)
        ap.add_argument('--profile', help='video bitrate ladder profile', dest='bitrate_profile',
                        default='hd', choices=[p.lower() for p in BitrateProfiles.keys()])
        ap.add_argument('--input', '-i', help='Input audio/video file',
                        required=True, dest='source')
        ap.add_argument('--kid', help='Key ID ("random" = auto generate KID)', nargs="*")
        ap.add_argument('--key', help='Encryption Key', nargs="*")
        ap.add_argument('-v', '--verbose', help='Verbose mode', action="store_true")
        ap.add_argument('--output', '-o', help='Output directory', dest='output', required=True)
        ap.add_argument('--prefix', '-p', help='Prefix for output files', required=True)
        args: argparse.Namespace = ap.parse_args(argv)
        mc_args: dict[str, Any] = {**vars(args)}
        mc_args["bitrate_profile"] = BitrateProfiles.from_string(args.bitrate_profile)
        mc_args["source"] = Path(args.source)
        rv = MediaCreateOptions(**mc_args)
        return rv
