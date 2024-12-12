export const defaultFullOptions = {
  "abr": true,
  "audioCodec": "mp4a",
  "audioDescription": null,
  "audioErrors": [],
  "availabilityStartTime": "year",
  "bugCompatibility": [],
  "clearkey": {
    "licenseUrl": null
  },
  "clockDrift": null,
  "dashjsVersion": null,
  "drmSelection": [],
  "eventTypes": [],
  "failureCount": null,
  "leeway": 16,
  "mainAudio": null,
  "mainText": null,
  "manifestErrors": [],
  "marlin": {
    "licenseUrl": null
  },
  "minimumUpdatePeriod": null,
  "mode": "vod",
  "ntpSources": [],
  "patch": false,
  "ping": {
    "count": 0,
    "duration": 200,
    "inband": true,
    "interval": 1000,
    "start": 0,
    "timescale": 100,
    "value": "0",
    "version": 0
  },
  "playready": {
    "licenseUrl": null,
    "piff": true,
    "version": null
  },
  "scte35": {
    "count": 0,
    "duration": 200,
    "inband": true,
    "interval": 1000,
    "program_id": 1620,
    "start": 0,
    "timescale": 100,
    "value": "",
    "version": 0
  },
  "segmentTimeline": false,
  "shakaVersion": null,
  "textCodec": null,
  "textErrors": [],
  "textLanguage": null,
  "timeShiftBufferDepth": 1800,
  "updateCount": null,
  "useBaseUrls": true,
  "utcMethod": null,
  "utcValue": null,
  "videoCorruption": [],
  "videoCorruptionFrameCount": null,
  "videoErrors": [],
  "videoPlayer": "native"
};
export const defaultShortOptions = {
  "ab": "1",
  "ac": "mp4a",
  "ad": null,
  "ahe": [],
  "ast": "year",
  "base": "1",
  "bug": "",
  "clearkey__la_url": null,
  "dft": null,
  "djVer": null,
  "drm": "",
  "evs": "",
  "hfc": null,
  "lee": 16,
  "ma": null,
  "marlin__la_url": null,
  "mhe": [],
  "mt": null,
  "mup": null,
  "ntps": "",
  "patch": "0",
  "ping__count": "0",
  "ping__duration": "200",
  "ping__inband": "1",
  "ping__interval": "1000",
  "ping__start": "0",
  "ping__timescale": "100",
  "ping__value": "0",
  "ping__version": "0",
  "playready__la_url": null,
  "playready__piff": "1",
  "playready__version": null,
  "scte35__count": "0",
  "scte35__duration": "200",
  "scte35__inband": "1",
  "scte35__interval": "1000",
  "scte35__program_id": "1620",
  "scte35__start": "0",
  "scte35__timescale": "100",
  "scte35__value": "",
  "scte35__version": "0",
  "skVer": null,
  "st": "0",
  "tbd": 1800,
  "tc": null,
  "the": [],
  "tl": null,
  "uc": null,
  "utc": null,
  "utv": null,
  "vcfc": null,
  "vcor": [],
  "vhe": [],
  "vp": "native"
};
export const defaultCgiOptions = {
  "abr": "1",
  "acodec": "mp4a",
  "ad_audio": null,
  "aerr": [],
  "base": "1",
  "bugs": "",
  "clearkey__la_url": null,
  "dashjs": null,
  "depth": 1800,
  "drift": null,
  "drm": "",
  "events": "",
  "failures": null,
  "frames": null,
  "leeway": 16,
  "main_audio": null,
  "main_text": null,
  "marlin__la_url": null,
  "merr": [],
  "mup": null,
  "ntp_servers": "",
  "patch": "0",
  "ping__count": "0",
  "ping__duration": "200",
  "ping__inband": "1",
  "ping__interval": "1000",
  "ping__start": "0",
  "ping__timescale": "100",
  "ping__value": "0",
  "ping__version": "0",
  "player": "native",
  "playready__la_url": null,
  "playready__piff": "1",
  "playready__version": null,
  "scte35__count": "0",
  "scte35__duration": "200",
  "scte35__inband": "1",
  "scte35__interval": "1000",
  "scte35__program_id": "1620",
  "scte35__start": "0",
  "scte35__timescale": "100",
  "scte35__value": "",
  "scte35__version": "0",
  "shaka": null,
  "start": "year",
  "tcodec": null,
  "terr": [],
  "time": null,
  "time_value": null,
  "timeline": "0",
  "tlang": null,
  "update": null,
  "vcorrupt": [],
  "verr": []
};

export const drmSystems = ["clearkey", "marlin", "playready"];

export const fieldGroups = [
  {
    "fields": [
      {
        "featured": true,
        "fullName": "abr",
        "name": "abr",
        "prefix": "",
        "shortName": "ab",
        "text": "Enable or disable adaptive bitrate",
        "title": "Adaptive bitrate",
        "type": "checkbox",
        "value": true
      },
      {
        "featured": true,
        "fullName": "audioCodec",
        "name": "acodec",
        "options": [
          {
            "selected": true,
            "title": "HEAAC codec",
            "value": "mp4a"
          },
          {
            "selected": false,
            "title": "EAC3 codec",
            "value": "ec-3"
          },
          {
            "selected": false,
            "title": "Any codec",
            "value": "any"
          }
        ],
        "prefix": "",
        "shortName": "ac",
        "text": "Filter audio adaptation sets by audio codec (AAC or E-AC3)",
        "title": "Audio Codec",
        "type": "select",
        "value": "mp4a"
      },
      {
        "featured": true,
        "fullName": "eventTypes",
        "multiple": true,
        "name": "events",
        "options": [
          {
            "selected": false,
            "title": "--",
            "value": ""
          },
          {
            "selected": false,
            "title": "ping",
            "value": "ping"
          },
          {
            "selected": false,
            "title": "scte35",
            "value": "scte35"
          }
        ],
        "prefix": "",
        "shortName": "evs",
        "text": "A comma separated list of event formats",
        "title": "DASH events",
        "type": "select",
        "value": []
      },
      {
        "featured": true,
        "fullName": "segmentTimeline",
        "name": "timeline",
        "prefix": "",
        "shortName": "st",
        "text": "Enable or disable segment timeline",
        "title": "Segment timeline",
        "type": "checkbox",
        "value": false
      },
      {
        "featured": true,
        "fullName": "utcMethod",
        "name": "time",
        "options": [
          {
            "selected": false,
            "title": "--",
            "value": ""
          },
          {
            "selected": false,
            "title": "direct",
            "value": "direct"
          },
          {
            "selected": false,
            "title": "head",
            "value": "head"
          },
          {
            "selected": false,
            "title": "http-ntp",
            "value": "http-ntp"
          },
          {
            "selected": false,
            "title": "iso",
            "value": "iso"
          },
          {
            "selected": false,
            "title": "ntp",
            "value": "ntp"
          },
          {
            "selected": false,
            "title": "sntp",
            "value": "sntp"
          },
          {
            "selected": false,
            "title": "xsd",
            "value": "xsd"
          }
        ],
        "prefix": "",
        "shortName": "utc",
        "text": "Select UTCTiming element method.",
        "title": "UTC timing method",
        "type": "select",
        "value": null
      },
      {
        "featured": true,
        "fullName": "videoPlayer",
        "name": "player",
        "options": [
          {
            "selected": true,
            "title": "Native video element",
            "value": "native"
          },
          {
            "selected": false,
            "title": "dash.js",
            "value": "dashjs"
          },
          {
            "selected": false,
            "title": "Shaka",
            "value": "shaka"
          }
        ],
        "prefix": "",
        "shortName": "vp",
        "text": "Native or MSE playback control",
        "title": "Video Player",
        "type": "select",
        "value": "native"
      }
    ],
    "name": "general",
    "title": "General Options"
  },
  {
    "fields": [
      {
        "featured": false,
        "fullName": "audioDescription",
        "name": "ad_audio",
        "prefix": "",
        "shortName": "ad",
        "text": "Select audio AdaptationSet that will be marked as a broadcast-mix audio description track",
        "title": "Audio Description",
        "type": "audio_representation",
        "value": null
      },
      {
        "datalist_type": "text",
        "featured": false,
        "fullName": "availabilityStartTime",
        "name": "start",
        "options": [
          {
            "selected": true,
            "title": "year",
            "value": "year"
          },
          {
            "selected": false,
            "title": "today",
            "value": "today"
          },
          {
            "selected": false,
            "title": "month",
            "value": "month"
          },
          {
            "selected": false,
            "title": "epoch",
            "value": "epoch"
          },
          {
            "selected": false,
            "title": "now",
            "value": "now"
          }
        ],
        "prefix": "",
        "shortName": "ast",
        "text": "Sets availabilityStartTime for live streams",
        "title": "Availability start time",
        "type": "datalist",
        "value": "year"
      },
      {
        "featured": false,
        "fullName": "bugCompatibility",
        "name": "bugs",
        "options": [
          {
            "selected": false,
            "title": "--",
            "value": ""
          },
          {
            "selected": false,
            "title": "saio",
            "value": "saio"
          }
        ],
        "prefix": "",
        "shortName": "bug",
        "text": "Produce a stream with known bugs",
        "title": "Bug compatibility",
        "type": "select",
        "value": []
      },
      {
        "featured": false,
        "fullName": "clockDrift",
        "name": "drift",
        "options": [
          {
            "selected": false,
            "title": "--",
            "value": ""
          },
          {
            "selected": false,
            "title": "10",
            "value": "10"
          }
        ],
        "prefix": "",
        "shortName": "dft",
        "text": "Number of seconds of delay to add to wall clock time",
        "title": "Clock drift",
        "type": "number",
        "value": null
      },
      {
        "datalist_type": "number",
        "featured": false,
        "fullName": "leeway",
        "name": "leeway",
        "options": [
          {
            "selected": false,
            "title": "16",
            "value": "16"
          },
          {
            "selected": false,
            "title": "60",
            "value": "60"
          },
          {
            "selected": false,
            "title": "0",
            "value": "0"
          }
        ],
        "prefix": "",
        "shortName": "lee",
        "text": "Number of seconds after a fragment has expired before it becomes unavailable",
        "title": "Fragment expiration leeway",
        "type": "datalist",
        "value": 16
      },
      {
        "featured": false,
        "fullName": "mainAudio",
        "name": "main_audio",
        "prefix": "",
        "shortName": "ma",
        "text": "Select audio AdaptationSet that will be given the \"main\" role",
        "title": "Main audio track",
        "type": "audio_representation",
        "value": null
      },
      {
        "featured": false,
        "fullName": "mainText",
        "name": "main_text",
        "prefix": "",
        "shortName": "mt",
        "text": "Select text AdaptationSet that will be given the \"main\" role",
        "title": "Main text track",
        "type": "text_representation",
        "value": null
      },
      {
        "datalist_type": "number",
        "featured": false,
        "fullName": "minimumUpdatePeriod",
        "name": "mup",
        "options": [
          {
            "selected": false,
            "title": "Every 2 fragments",
            "value": ""
          },
          {
            "selected": false,
            "title": "Never",
            "value": "-1"
          },
          {
            "selected": false,
            "title": "Every fragment",
            "value": "4"
          },
          {
            "selected": false,
            "title": "Every 30 seconds",
            "value": "30"
          }
        ],
        "prefix": "",
        "shortName": "mup",
        "text": "Specify minimumUpdatePeriod (in seconds) or -1 to disable updates",
        "title": "Minimum update period",
        "type": "datalist",
        "value": null
      },
      {
        "featured": false,
        "fullName": "ntpSources",
        "name": "ntp_servers",
        "options": [
          {
            "selected": false,
            "title": "--",
            "value": ""
          },
          {
            "selected": false,
            "title": "europe-ntp",
            "value": "europe-ntp"
          },
          {
            "selected": false,
            "title": "google",
            "value": "google"
          }
        ],
        "prefix": "",
        "shortName": "ntps",
        "text": "List of servers to use for NTP requests",
        "title": "NTP time servers",
        "type": "select",
        "value": []
      },
      {
        "featured": false,
        "fullName": "textCodec",
        "name": "tcodec",
        "options": [
          {
            "selected": false,
            "title": "Any codec",
            "value": ""
          },
          {
            "selected": false,
            "title": "im1t codec",
            "value": "im1t|etd1"
          }
        ],
        "prefix": "",
        "shortName": "tc",
        "text": "Filter text adaptation sets by text codec",
        "title": "Text Codec",
        "type": "select",
        "value": null
      },
      {
        "featured": false,
        "fullName": "textLanguage",
        "name": "tlang",
        "prefix": "",
        "shortName": "tl",
        "text": "Filter text adaptation sets by language",
        "title": "Text Language",
        "type": "",
        "value": null
      },
      {
        "featured": false,
        "fullName": "useBaseUrls",
        "name": "base",
        "prefix": "",
        "shortName": "base",
        "text": "Include a BaseURL element?",
        "title": "Use BaseURLs",
        "type": "checkbox",
        "value": true
      },
      {
        "featured": false,
        "fullName": "patch",
        "name": "patch",
        "prefix": "",
        "shortName": "patch",
        "text": "Use MPD patches for live streams",
        "title": "Use MPD patches",
        "type": "checkbox",
        "value": false
      },
      {
        "datalist_type": "number",
        "featured": false,
        "fullName": "timeShiftBufferDepth",
        "name": "depth",
        "options": [
          {
            "selected": false,
            "title": "1800",
            "value": "1800"
          },
          {
            "selected": false,
            "title": "30",
            "value": "30"
          }
        ],
        "prefix": "",
        "shortName": "tbd",
        "text": "Number of seconds for timeShiftBufferDepth",
        "title": "timeShiftBufferDepth size",
        "type": "datalist",
        "value": 1800
      }
    ],
    "name": "advanced",
    "title": "Advanced Options"
  },
  {
    "fields": [
      {
        "className": "drm-checkbox",
        "name": "clearkey__enabled",
        "prefix": "clearkey",
        "text": "Enable Clearkey DRM support?",
        "title": "Clearkey DRM",
        "type": "checkbox",
        "value": false
      },
      {
        "featured": false,
        "fullName": "licenseUrl",
        "name": "clearkey__la_url",
        "prefix": "clearkey",
        "shortName": "clu",
        "text": "Override the Clearkey license URL field",
        "title": "Clearkey LA_URL",
        "type": "",
        "value": null
      },
      {
        "featured": true,
        "fullName": "drmLocation",
        "name": "clearkey__drmloc",
        "options": [
          {
            "selected": true,
            "title": "All locations",
            "value": ""
          },
          {
            "selected": false,
            "title": "mspr:pro element in MPD",
            "value": "pro"
          },
          {
            "selected": false,
            "title": "dash:cenc element in MPD",
            "value": "cenc"
          },
          {
            "selected": false,
            "title": "PSSH in init segment",
            "value": "moov"
          },
          {
            "selected": false,
            "title": "mspr:pro + dash:cenc in MPD",
            "value": "cenc-pro"
          },
          {
            "selected": false,
            "title": "mspr:pro MPD + PSSH init",
            "value": "moov-pro"
          },
          {
            "selected": false,
            "title": "dash:cenc MPD + PSSH init",
            "value": "cenc-moov"
          }
        ],
        "prefix": "clearkey",
        "rowClass": "row mb-3 drm-location prefix-clearkey",
        "shortName": "dloc",
        "text": "Location to place DRM data",
        "title": "Clearkey location",
        "type": "select",
        "value": ""
      }
    ],
    "name": "clearkey",
    "title": "Clearkey Options"
  },
  {
    "fields": [
      {
        "className": "drm-checkbox",
        "name": "marlin__enabled",
        "prefix": "marlin",
        "text": "Enable Marlin DRM support?",
        "title": "Marlin DRM",
        "type": "checkbox",
        "value": false
      },
      {
        "featured": false,
        "fullName": "licenseUrl",
        "name": "marlin__la_url",
        "prefix": "marlin",
        "shortName": "mlu",
        "text": "Override the Marlin S-URL field",
        "title": "Marlin LA_URL",
        "type": "",
        "value": null
      },
      {
        "featured": true,
        "fullName": "drmLocation",
        "name": "marlin__drmloc",
        "options": [
          {
            "selected": true,
            "title": "All locations",
            "value": ""
          },
          {
            "selected": false,
            "title": "mspr:pro element in MPD",
            "value": "pro"
          },
          {
            "selected": false,
            "title": "dash:cenc element in MPD",
            "value": "cenc"
          },
          {
            "selected": false,
            "title": "PSSH in init segment",
            "value": "moov"
          },
          {
            "selected": false,
            "title": "mspr:pro + dash:cenc in MPD",
            "value": "cenc-pro"
          },
          {
            "selected": false,
            "title": "mspr:pro MPD + PSSH init",
            "value": "moov-pro"
          },
          {
            "selected": false,
            "title": "dash:cenc MPD + PSSH init",
            "value": "cenc-moov"
          }
        ],
        "prefix": "marlin",
        "rowClass": "row mb-3 drm-location prefix-marlin",
        "shortName": "dloc",
        "text": "Location to place DRM data",
        "title": "Marlin location",
        "type": "select",
        "value": ""
      }
    ],
    "name": "marlin",
    "title": "Marlin Options"
  },
  {
    "fields": [
      {
        "featured": false,
        "fullName": "count",
        "name": "ping__count",
        "prefix": "ping",
        "shortName": "pinCoun",
        "text": "",
        "title": "Ping count",
        "type": "number",
        "value": 0
      },
      {
        "featured": false,
        "fullName": "duration",
        "name": "ping__duration",
        "prefix": "ping",
        "shortName": "pinDura",
        "text": "",
        "title": "Ping duration",
        "type": "number",
        "value": 200
      },
      {
        "featured": false,
        "fullName": "inband",
        "name": "ping__inband",
        "prefix": "ping",
        "shortName": "pinInba",
        "text": "",
        "title": "Ping inband",
        "type": "checkbox",
        "value": true
      },
      {
        "featured": false,
        "fullName": "interval",
        "name": "ping__interval",
        "prefix": "ping",
        "shortName": "pinInte",
        "text": "",
        "title": "Ping interval",
        "type": "number",
        "value": 1000
      },
      {
        "featured": false,
        "fullName": "start",
        "name": "ping__start",
        "prefix": "ping",
        "shortName": "pinStar",
        "text": "",
        "title": "Ping start",
        "type": "number",
        "value": 0
      },
      {
        "featured": false,
        "fullName": "timescale",
        "name": "ping__timescale",
        "prefix": "ping",
        "shortName": "pinTime",
        "text": "",
        "title": "Ping timescale",
        "type": "number",
        "value": 100
      },
      {
        "featured": false,
        "fullName": "value",
        "name": "ping__value",
        "prefix": "ping",
        "shortName": "pinValu",
        "text": "",
        "title": "Ping value",
        "type": "text",
        "value": "0"
      },
      {
        "featured": false,
        "fullName": "version",
        "name": "ping__version",
        "prefix": "ping",
        "shortName": "pinVers",
        "text": "",
        "title": "Ping version",
        "type": "number",
        "value": 0
      }
    ],
    "name": "ping",
    "title": "Ping Options"
  },
  {
    "fields": [
      {
        "className": "drm-checkbox",
        "name": "playready__enabled",
        "prefix": "playready",
        "text": "Enable Playready DRM support?",
        "title": "Playready DRM",
        "type": "checkbox",
        "value": false
      },
      {
        "featured": false,
        "fullName": "licenseUrl",
        "name": "playready__la_url",
        "prefix": "playready",
        "shortName": "plu",
        "text": "Override the Playready LA_URL field",
        "title": "Playready LA_URL",
        "type": "",
        "value": null
      },
      {
        "featured": false,
        "fullName": "piff",
        "name": "playready__piff",
        "prefix": "playready",
        "shortName": "pff",
        "text": "Include PIFF sample encryption data",
        "title": "Playready PIFF",
        "type": "checkbox",
        "value": true
      },
      {
        "featured": false,
        "fullName": "version",
        "name": "playready__version",
        "options": [
          {
            "selected": false,
            "title": "--",
            "value": ""
          },
          {
            "selected": false,
            "title": "1.0",
            "value": "1.0"
          },
          {
            "selected": false,
            "title": "2.0",
            "value": "2.0"
          },
          {
            "selected": false,
            "title": "3.0",
            "value": "3.0"
          },
          {
            "selected": false,
            "title": "4.0",
            "value": "4.0"
          }
        ],
        "prefix": "playready",
        "shortName": "pvn",
        "text": "Set the PlayReady version compatibility for this stream",
        "title": "Playready Version",
        "type": "select",
        "value": null
      },
      {
        "featured": true,
        "fullName": "drmLocation",
        "name": "playready__drmloc",
        "options": [
          {
            "selected": true,
            "title": "All locations",
            "value": ""
          },
          {
            "selected": false,
            "title": "mspr:pro element in MPD",
            "value": "pro"
          },
          {
            "selected": false,
            "title": "dash:cenc element in MPD",
            "value": "cenc"
          },
          {
            "selected": false,
            "title": "PSSH in init segment",
            "value": "moov"
          },
          {
            "selected": false,
            "title": "mspr:pro + dash:cenc in MPD",
            "value": "cenc-pro"
          },
          {
            "selected": false,
            "title": "mspr:pro MPD + PSSH init",
            "value": "moov-pro"
          },
          {
            "selected": false,
            "title": "dash:cenc MPD + PSSH init",
            "value": "cenc-moov"
          }
        ],
        "prefix": "playready",
        "rowClass": "row mb-3 drm-location prefix-playready",
        "shortName": "dloc",
        "text": "Location to place DRM data",
        "title": "Playready location",
        "type": "select",
        "value": ""
      }
    ],
    "name": "playready",
    "title": "Playready Options"
  },
  {
    "fields": [
      {
        "featured": false,
        "fullName": "count",
        "name": "scte35__count",
        "prefix": "scte35",
        "shortName": "sctCoun",
        "text": "",
        "title": "Scte35 count",
        "type": "number",
        "value": 0
      },
      {
        "featured": false,
        "fullName": "duration",
        "name": "scte35__duration",
        "prefix": "scte35",
        "shortName": "sctDura",
        "text": "",
        "title": "Scte35 duration",
        "type": "number",
        "value": 200
      },
      {
        "featured": false,
        "fullName": "inband",
        "name": "scte35__inband",
        "prefix": "scte35",
        "shortName": "sctInba",
        "text": "",
        "title": "Scte35 inband",
        "type": "checkbox",
        "value": true
      },
      {
        "featured": false,
        "fullName": "interval",
        "name": "scte35__interval",
        "prefix": "scte35",
        "shortName": "sctInte",
        "text": "",
        "title": "Scte35 interval",
        "type": "number",
        "value": 1000
      },
      {
        "featured": false,
        "fullName": "program_id",
        "name": "scte35__program_id",
        "prefix": "scte35",
        "shortName": "sctProg",
        "text": "",
        "title": "Scte35 program_id",
        "type": "number",
        "value": 1620
      },
      {
        "featured": false,
        "fullName": "start",
        "name": "scte35__start",
        "prefix": "scte35",
        "shortName": "sctStar",
        "text": "",
        "title": "Scte35 start",
        "type": "number",
        "value": 0
      },
      {
        "featured": false,
        "fullName": "timescale",
        "name": "scte35__timescale",
        "prefix": "scte35",
        "shortName": "sctTime",
        "text": "",
        "title": "Scte35 timescale",
        "type": "number",
        "value": 100
      },
      {
        "featured": false,
        "fullName": "value",
        "name": "scte35__value",
        "prefix": "scte35",
        "shortName": "sctValu",
        "text": "",
        "title": "Scte35 value",
        "type": "text",
        "value": ""
      },
      {
        "featured": false,
        "fullName": "version",
        "name": "scte35__version",
        "prefix": "scte35",
        "shortName": "sctVers",
        "text": "",
        "title": "Scte35 version",
        "type": "number",
        "value": 0
      }
    ],
    "name": "scte35",
    "title": "Scte35 Options"
  }
];