// this file is auto-generated, do not edit!

// to re-generate this file, use the command:
// uv run -m dashlive.server.options.generate_types

export type DrmSystemType = "clearkey" | "marlin" | "playready";

export type ClearkeyOptionsType = {
  licenseUrl: string | null;
}

export type MarlinOptionsType = {
  licenseUrl: string | null;
}

export type PlayreadyOptionsType = {
  licenseUrl: string | null;
  piff: boolean;
  version: number | null;
}

export type PingOptionsType = {
  count: number;
  duration: number;
  inband: boolean;
  interval: number;
  start: number;
  timescale: number;
  value: string;
  version: number;
}

export type Scte35OptionsType = {
  count: number;
  duration: number;
  inband: boolean;
  interval: number;
  program_id: number;
  start: number;
  timescale: number;
  value: string | null;
  version: number;
}

export type OptionsContainerType = {
  abr: boolean;
  audioCodec: string;
  audioDescription: string | null;
  audioErrors: [number, string][];
  availabilityStartTime: Date | string;
  bugCompatibility: string[];
  clearkey: ClearkeyOptionsType;
  clockDrift: number | null;
  dashjsVersion: string | null;
  drmSelection: unknown[];
  eventTypes: string[];
  failureCount: number | null;
  forcePeriodDurations: boolean;
  leeway: number;
  mainAudio: string | null;
  mainText: string | null;
  manifestErrors: [number, string][];
  marlin: MarlinOptionsType;
  minimumUpdatePeriod: number | null;
  mode: string;
  ntpSources: string[];
  patch: boolean;
  ping: PingOptionsType;
  playready: PlayreadyOptionsType;
  scte35: Scte35OptionsType;
  segmentTimeline: boolean;
  shakaVersion: string | null;
  textCodec: string | null;
  textErrors: [number, string][];
  textLanguage: string | null;
  textPreference: string | null;
  timeShiftBufferDepth: number;
  updateCount: number | null;
  useBaseUrls: boolean;
  utcMethod: string | null;
  utcValue: string | null;
  videoCorruption: string[];
  videoCorruptionFrameCount: number | null;
  videoErrors: [number, string][];
  videoPlayer: string | null;
}

export type ShortOptionsContainerType = {
  ab: boolean;
  ac: string;
  ad: string | null;
  ahe: [number, string][];
  ast: Date | string;
  bug: string[];
  clu: string | null;
  dft: number | null;
  djVer: string | null;
  drm: unknown[];
  evs: string[];
  hfc: number | null;
  fpd: boolean;
  lee: number;
  ma: string | null;
  mt: string | null;
  mhe: [number, string][];
  mlu: string | null;
  mup: number | null;
  md: string;
  ntps: string[];
  patch: boolean;
  pinCoun: number;
  pinDura: number;
  pinInba: boolean;
  pinInte: number;
  pinStar: number;
  pinTime: number;
  pinValu: string;
  pinVers: number;
  plu: string | null;
  pff: boolean;
  pvn: number | null;
  sctCoun: number;
  sctDura: number;
  sctInba: boolean;
  sctInte: number;
  sctProg: number;
  sctStar: number;
  sctTime: number;
  sctValu: string | null;
  sctVers: number;
  st: boolean;
  skVer: string | null;
  tc: string | null;
  the: [number, string][];
  tl: string | null;
  ptxLang: string | null;
  tbd: number;
  uc: number | null;
  base: boolean;
  utc: string | null;
  utv: string | null;
  vcor: string[];
  vcfc: number | null;
  vhe: [number, string][];
  vp: string | null;
}

export type CgiOptionsContainerType = {
  abr: boolean;
  acodec: string;
  ad_audio: string | null;
  aerr: [number, string][];
  start: Date | string;
  bugs: string[];
  clearkey__la_url: string | null;
  drift: number | null;
  dashjs: string | null;
  drm: unknown[];
  events: string[];
  failures: number | null;
  periodDur: boolean;
  leeway: number;
  main_audio: string | null;
  main_text: string | null;
  merr: [number, string][];
  marlin__la_url: string | null;
  mup: number | null;
  mode: string;
  ntp_servers: string[];
  patch: boolean;
  ping__count: number;
  ping__duration: number;
  ping__inband: boolean;
  ping__interval: number;
  ping__start: number;
  ping__timescale: number;
  ping__value: string;
  ping__version: number;
  playready__la_url: string | null;
  playready__piff: boolean;
  playready__version: number | null;
  scte35__count: number;
  scte35__duration: number;
  scte35__inband: boolean;
  scte35__interval: number;
  scte35__program_id: number;
  scte35__start: number;
  scte35__timescale: number;
  scte35__value: string | null;
  scte35__version: number;
  timeline: boolean;
  shaka: string | null;
  tcodec: string | null;
  terr: [number, string][];
  tlang: string | null;
  text_pref: string | null;
  depth: number;
  update: number | null;
  base: boolean;
  time: string | null;
  time_value: string | null;
  vcorrupt: string[];
  frames: number | null;
  verr: [number, string][];
  player: string | null;
}
