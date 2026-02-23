# this file is auto-generated, do not edit!
# to re-generate this file, use the command:
# uv run -m dashlive.server.options.generate_types

import datetime
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


@dataclass
class ShortOptionsContainerType(OptionsGroup):
    ab: bool = True
    ac: str = field(default="mp4a")
    ad: str | None = None
    ahe: list[tuple[int, str]] = field(default_factory=list)
    ast: datetime.datetime | str = field(default="year")
    bug: list[str] = field(default_factory=list)
    clu: str | None = None
    dft: int | None = None
    djVer: str | None = None
    drm: list[tuple] = field(default_factory=list)
    evs: list[str] = field(default_factory=list)
    hfc: int | None = None
    fpd: bool = False
    lee: int = 16
    ma: str | None = None
    mt: str | None = None
    mhe: list[tuple[int, str]] = field(default_factory=list)
    mlu: str | None = None
    mup: int | None = None
    md: str = field(default="vod")
    ntps: list[str] = field(default_factory=list)
    patch: bool = False
    pinCoun: int = 0
    pinDura: int = 200
    pinInba: bool = True
    pinInte: int = 1000
    pinStar: int = 0
    pinTime: int = 100
    pinValu: str = field(default="0")
    pinVers: int = 0
    plu: str | None = None
    pff: bool = True
    pvn: float | None = None
    sctCoun: int = 0
    sctDura: int = 200
    sctInba: bool = True
    sctInte: int = 1000
    sctProg: int = 1620
    sctStar: int = 0
    sctTime: int = 100
    sctValu: str | None = None
    sctVers: int = 0
    st: bool = False
    skVer: str | None = None
    tc: str | None = None
    the: list[tuple[int, str]] = field(default_factory=list)
    tl: str | None = None
    ptxLang: str | None = None
    tbd: int = 1800
    uc: int | None = None
    base: bool = True
    utc: str | None = None
    utv: str | None = None
    vcor: list[str] = field(default_factory=list)
    vcfc: int | None = None
    vhe: list[tuple[int, str]] = field(default_factory=list)
    vp: str | None = field(default="native")


@dataclass
class CgiOptionsContainerType(OptionsGroup):
    abr: bool = True
    acodec: str = field(default="mp4a")
    ad_audio: str | None = None
    aerr: list[tuple[int, str]] = field(default_factory=list)
    start: datetime.datetime | str = field(default="year")
    bugs: list[str] = field(default_factory=list)
    clearkey__la_url: str | None = None
    drift: int | None = None
    dashjs: str | None = None
    drm: list[tuple] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    failures: int | None = None
    periodDur: bool = False
    leeway: int = 16
    main_audio: str | None = None
    main_text: str | None = None
    merr: list[tuple[int, str]] = field(default_factory=list)
    marlin__la_url: str | None = None
    mup: int | None = None
    mode: str = field(default="vod")
    ntp_servers: list[str] = field(default_factory=list)
    patch: bool = False
    ping__count: int = 0
    ping__duration: int = 200
    ping__inband: bool = True
    ping__interval: int = 1000
    ping__start: int = 0
    ping__timescale: int = 100
    ping__value: str = field(default="0")
    ping__version: int = 0
    playready__la_url: str | None = None
    playready__piff: bool = True
    playready__version: float | None = None
    scte35__count: int = 0
    scte35__duration: int = 200
    scte35__inband: bool = True
    scte35__interval: int = 1000
    scte35__program_id: int = 1620
    scte35__start: int = 0
    scte35__timescale: int = 100
    scte35__value: str | None = None
    scte35__version: int = 0
    timeline: bool = False
    shaka: str | None = None
    tcodec: str | None = None
    terr: list[tuple[int, str]] = field(default_factory=list)
    tlang: str | None = None
    text_pref: str | None = None
    depth: int = 1800
    update: int | None = None
    base: bool = True
    time: str | None = None
    time_value: str | None = None
    vcorrupt: list[str] = field(default_factory=list)
    frames: int | None = None
    verr: list[tuple[int, str]] = field(default_factory=list)
    player: str | None = field(default="native")
