# this file is auto-generated, do not edit!
# to re-generate this file, use the command:
# uv run -m dashlive.server.options.generate_types

from typing import Any
from dataclasses import dataclass, field
from .options_group import OptionsGroup

@dataclass
class ClearkeyOptionsType(OptionsGroup):
    licenseUrl: str | None = None


@dataclass
class MarlinOptionsType(OptionsGroup):
    licenseUrl: str | None = None


@dataclass
class PlayreadyOptionsType(OptionsGroup):
    licenseUrl: str | None = None
    piff: bool = True
    version: float | None = None


@dataclass
class PingOptionsType(OptionsGroup):
    count: int = 0
    duration: int = 200
    inband: bool = True
    interval: int = 1000
    start: int = 0
    timescale: int = 100
    value: str = field(default="0")
    version: int = 0


@dataclass
class Scte35OptionsType(OptionsGroup):
    count: int = 0
    duration: int = 200
    inband: bool = True
    interval: int = 1000
    program_id: int = 1620
    start: int = 0
    timescale: int = 100
    value: str | None = None
    version: int = 0


SUB_OPTION_PREFIX_MAP: dict[str, type] = {
    "clearkey": ClearkeyOptionsType,
    "marlin": MarlinOptionsType,
    "playready": PlayreadyOptionsType,
    "ping": PingOptionsType,
    "scte35": Scte35OptionsType,
}

@dataclass
class OptionsContainerType(OptionsGroup):
    abr: bool = True
    audioCodec: str = field(default="mp4a")
    audioDescription: str | None = None
    audioErrors: list[tuple[int, str]] = field(default_factory=list)
    availabilityStartTime: datetime.datetime | str = field(default="year")
    bugCompatibility: list[str] = field(default_factory=list)
    clearkey: ClearkeyOptionsType = field(default_factory=ClearkeyOptionsType)
    clockDrift: int | None = None
    dashjsVersion: str | None = None
    drmSelection: list[tuple] = field(default_factory=list)
    eventTypes: list[str] = field(default_factory=list)
    failureCount: int | None = None
    forcePeriodDurations: bool = False
    leeway: int = 16
    mainAudio: str | None = None
    mainText: str | None = None
    manifestErrors: list[tuple[int, str]] = field(default_factory=list)
    marlin: MarlinOptionsType = field(default_factory=MarlinOptionsType)
    minimumUpdatePeriod: int | None = None
    mode: str = field(default="vod")
    ntpSources: list[str] = field(default_factory=list)
    patch: bool = False
    ping: PingOptionsType = field(default_factory=PingOptionsType)
    playready: PlayreadyOptionsType = field(default_factory=PlayreadyOptionsType)
    scte35: Scte35OptionsType = field(default_factory=Scte35OptionsType)
    segmentTimeline: bool = False
    shakaVersion: str | None = None
    textCodec: str | None = None
    textErrors: list[tuple[int, str]] = field(default_factory=list)
    textLanguage: str | None = None
    textPreference: str | None = None
    timeShiftBufferDepth: int = 1800
    updateCount: int | None = None
    useBaseUrls: bool = True
    utcMethod: str | None = None
    utcValue: str | None = None
    videoCorruption: list[str] = field(default_factory=list)
    videoCorruptionFrameCount: int | None = None
    videoErrors: list[tuple[int, str]] = field(default_factory=list)
    videoPlayer: str | None = field(default="native")
