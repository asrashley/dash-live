#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from typing import NotRequired, TypedDict

class FfmpegStreamJson(TypedDict):
    index: int
    codec_name: str
    duration: str
    codec_type: str  # 'video' or 'audio'
    profile: NotRequired[str]
    display_aspect_ratio: NotRequired[str]
    avg_frame_rate: NotRequired[str]
    width: NotRequired[int]
    height: NotRequired[int]
    sample_rate: NotRequired[str]
    channels: NotRequired[int]
    channel_layout: NotRequired[str]


@dataclass
class StreamInfoBase:
    content_type: str  # 'video', 'audio', or 'text'
    index: int
    codec: str
    duration: float  # in seconds
    profile: str | None


@dataclass
class VideoStreamInfo(StreamInfoBase):
    display_aspect_ratio: str | None
    width: int
    height: int
    framerate: float | None

    @classmethod
    def from_json(cls, info: FfmpegStreamJson) -> "VideoStreamInfo":
        framerate: float | None
        try:
            framerate = VideoStreamInfo.framerate_from_str(
                info["avg_frame_rate"])  # pyright: ignore[reportTypedDictNotRequiredAccess]
        except KeyError:
            framerate = None
        return VideoStreamInfo(
            content_type=info["codec_type"],
            index=info["index"],
            codec=info["codec_name"],
            duration=float(info["duration"]),
            profile=info.get("profile"),
            width=info.get("width", 0),
            height=info.get("height", 0),
            framerate=framerate,
            display_aspect_ratio=info.get("display_aspect_ratio")
        )

    @staticmethod
    def framerate_from_str(fps: str) -> float:
        if '/' in fps:
            n, d = fps.split('/')
            if float(d) > 0:
                rv: float = round(1000 * float(n) / float(d))
                return rv / 1000
            return float(n)
        return float(int(fps, 10))


@dataclass
class AudioStreamInfo(StreamInfoBase):
    sample_rate: int
    channels: int
    channel_layout: str

    @classmethod
    def from_json(cls, info: FfmpegStreamJson) -> "AudioStreamInfo":
        return AudioStreamInfo(
            content_type=info["codec_type"],
            index=info["index"],
            codec=info["codec_name"],
            duration=float(info["duration"]),
            profile=info.get("profile"),
            sample_rate=int(info.get("sample_rate", "0"), 10),
            channels=info.get("channels", 2),
            channel_layout=info.get("channel_layout", "stereo")
        )


class FfmpegFormatJson(TypedDict):
    duration: str
    filename: str
    nb_streams: int
    nb_programs: int
    format_name: str
    start_time: str
    size: str
    bit_rate: str


@dataclass
class MediaFormatInfo:
    duration: float  # in seconds
    format_name: str
    start_time: float  # in seconds
    size: int  # in bytes
    bit_rate: int  # in bits/sec

    @classmethod
    def from_json(cls, fmt: FfmpegFormatJson) -> "MediaFormatInfo":
        return MediaFormatInfo(
            duration=float(fmt["duration"]),
            format_name=fmt["format_name"],
            start_time=float(fmt["start_time"]),
            size=int(fmt["size"], 10),
            bit_rate=int(fmt["bit_rate"], 10)
        )


class FfmpegMediaJson(TypedDict):
    streams: list[FfmpegStreamJson]
    format: FfmpegFormatJson


@dataclass
class MediaProbeResults:
    format: MediaFormatInfo
    audio: list[AudioStreamInfo]
    video: list[VideoStreamInfo]

    @classmethod
    def from_json(cls, info: FfmpegMediaJson) -> "MediaProbeResults":
        format: MediaFormatInfo = MediaFormatInfo.from_json(info["format"])
        results = MediaProbeResults(format=format, audio=[], video=[])
        for stream in info["streams"]:
            if stream["codec_type"] == 'video':
                results.video.append(VideoStreamInfo.from_json(stream))
            elif stream["codec_type"] == 'audio':
                results.audio.append(AudioStreamInfo.from_json(stream))
        return results


class VideoFrameJson(TypedDict):
    key_frame: int
    pts: int
    duration: int
    pkt_pos: str
    pkt_size: str
    pict_type: str
    interlaced_frame: int
    top_field_first: int


@dataclass
class VideoFrameInfo:
    key_frame: bool
    pts: int
    duration: int
    pos: int
    size: int
    pict_type: str
    interlaced_frame: bool
    top_field_first: bool

    @classmethod
    def from_json(cls, js: VideoFrameJson) -> "VideoFrameInfo":
        return VideoFrameInfo(
            key_frame=js["key_frame"] != 0,
            pts=js["pts"],
            duration=js["duration"],
            pos=int(js["pkt_pos"], 10),
            size=int(js["pkt_size"], 10),
            pict_type=js["pict_type"],
            interlaced_frame=js["interlaced_frame"] != 0,
            top_field_first=js["top_field_first"] != 0)

class FfmpegVideoProbeJson(TypedDict):
    frames: list[VideoFrameJson]


class FfmpegHelper:
    @classmethod
    def probe_media_info(cls, src: Path) -> MediaProbeResults:
        info: FfmpegMediaJson = json.loads(subprocess.check_output([
            "ffprobe",
            "-v", "0",
            "-of", "json",
            "-show_format",
            "-show_streams",
            f"{src.absolute()}",
        ]))
        return MediaProbeResults.from_json(info)

    @classmethod
    def probe_video_frames(cls, src: Path) -> list[VideoFrameInfo]:
        ffmpeg_args: list[str] = [
            "ffprobe",
            "-v", "0",
            "-show_frames",
            "-print_format", "json",
            f"{src}",
        ]
        data: str = subprocess.check_output(
            ffmpeg_args, stderr=subprocess.STDOUT, text=True)
        probe: FfmpegVideoProbeJson = json.loads(data)
        results: list[VideoFrameInfo] = [VideoFrameInfo.from_json(f) for f in probe["frames"]]
        return results
