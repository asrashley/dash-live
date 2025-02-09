export const routeMap = {
  css: {
    title: "static style sheets",
    re: /\/static\/css\/(?<filename>[\w_.-]+)/,
    route: "/static/css/:filename",
    url: ({filename}) => `/static/css/${filename}`,
  },
  fonts: {
    title: "static fonts",
    re: /\/static\/fonts\/(?<filename>[\w_.-]+)/,
    route: "/static/fonts/:filename",
    url: ({filename}) => `/static/fonts/${filename}`,
  },
  icons: {
    title: "static icons",
    re: /\/static\/icons\/(?<filename>[\w_.-]+)/,
    route: "/static/icons/:filename",
    url: ({filename}) => `/static/icons/${filename}`,
  },
  images: {
    title: "static images",
    re: /\/static\/img\/(?<filename>[\w_.-]+)/,
    route: "/static/img/:filename",
    url: ({filename}) => `/static/img/${filename}`,
  },
  deleteKey: {
    title: "delete key pairs",
    re: /\/key\/(?<kpk>\d+)\/delete/,
    route: "/key/:kpk/delete",
    url: ({kpk}) => `/key/${kpk}/delete`,
  },
  editKey: {
    title: "Edit key pairs",
    re: /\/key\/(?<kpk>\d+)/,
    route: "/key/:kpk",
    url: ({kpk}) => `/key/${kpk}`,
  },
  addKey: {
    title: "Add key pairs",
    re: /\/key/,
    route: "/key",
    url: () => `/key`,
  },
  clearkey: {
    title: "W3C clearkey support",
    re: /\/clearkey/,
    route: "/clearkey",
    url: () => `/clearkey`,
  },
  dashMpdV1: {
    title: "DASH test stream (v1 URL)",
    re: /\/dash\/(?<manifest>[\w\-_]+\.mpd)/,
    route: "/dash/:manifest",
    url: ({manifest}) => `/dash/${manifest}`,
  },
  dashMpdV2: {
    title: "DASH test stream (v2 URL)",
    re: /\/dash\/(?<stream>\w+)\/(?<manifest>[\w\-_]+\.mpd)/,
    route: "/dash/:stream/:manifest",
    url: ({stream, manifest}) => `/dash/${stream}/${manifest}`,
  },
  dashMpdV3: {
    title: "DASH test stream",
    re: /\/dash\/(?<mode>(live|vod|odvod))\/(?<stream>\w+)\/(?<manifest>\w+)/,
    route: "/dash/:mode/:stream/:manifest",
    url: ({mode, stream, manifest}) => `/dash/${mode}/${stream}/${manifest}`,
  },
  mpdPatch: {
    title: "DASH manifest patch",
    re: /\/patch\/(?<stream>\w+)\/(?<manifest>\w+)\/(?<publish>\d+)/,
    route: "/patch/:stream/:manifest/:publish",
    url: ({stream, manifest, publish}) => `/patch/${stream}/${manifest}/${publish}`,
  },
  dashMediaBaseUrl: {
    title: "Used for generating BaseURL values",
    re: /\/dash\/(?<mode>(live|vod))\/(?<stream>\w+)\//,
    route: "/dash/:mode/:stream/",
    url: ({mode, stream}) => `/dash/${mode}/${stream}/`,
  },
  dashMedia: {
    title: "DASH fragment",
    re: /\/dash\/(?<mode>(live|vod))\/(?<stream>\w+)\/(?<filename>\w+)\/(?<segment_num>(\d+|init)).(?<ext>(mp4|m4v|m4a|m4s))/,
    route: "/dash/:mode/:stream/:filename/:segment_num.:ext",
    url: ({mode, stream, filename, segment_num, ext}) => `/dash/${mode}/${stream}/${filename}/${segment_num}.${ext}`,
  },
  dashMediaByTime: {
    title: "DASH fragment",
    re: /\/dash\/(?<mode>(live|vod))\/(?<stream>\w+)\/(?<filename>\w+)\/time\/(?<segment_time>\d+).(?<ext>(mp4|m4v|m4a|m4s))/,
    route: "/dash/:mode/:stream/:filename/time/:segment_time.:ext",
    url: ({mode, stream, filename, segment_time, ext}) => `/dash/${mode}/${stream}/${filename}/time/${segment_time}.${ext}`,
  },
  dashOdMediaBaseUrl: {
    title: "BaseURL for on-demand media",
    re: /\/dash\/odvod\/(?<stream>\w+)\//,
    route: "/dash/odvod/:stream/",
    url: ({stream}) => `/dash/odvod/${stream}/`,
  },
  dashOdMedia: {
    title: "DASH media file",
    re: /\/dash\/odvod\/(?<stream>\w+)\/(?<filename>[\w-]+).(?<ext>(mp4|m4v|m4a|m4s))/,
    route: "/dash/odvod/:stream/:filename.:ext",
    url: ({stream, filename, ext}) => `/dash/odvod/${stream}/${filename}.${ext}`,
  },
  indexMediaFile: {
    title: "Media information",
    re: /\/media\/index\/(?<mfid>\d+)/,
    route: "/media/index/:mfid",
    url: ({mfid}) => `/media/index/${mfid}`,
  },
  viewMediaSegment: {
    title: "Media Segment",
    re: /\/stream\/(?<spk>\d+)\/(?<mfid>\d+)\/segment\/(?<segnum>\d+)/,
    route: "/stream/:spk/:mfid/segment/:segnum",
    url: ({spk, mfid, segnum}) => `/stream/${spk}/${mfid}/segment/${segnum}`,
  },
  listMediaSegments: {
    title: "Media Segments",
    re: /\/stream\/(?<spk>\d+)\/(?<mfid>\d+)\/segments/,
    route: "/stream/:spk/:mfid/segments",
    url: ({spk, mfid}) => `/stream/${spk}/${mfid}/segments`,
  },
  mediaInfo: {
    title: "Media information",
    re: /\/stream\/(?<spk>\d+)\/(?<mfid>\d+)/,
    route: "/stream/:spk/:mfid",
    url: ({spk, mfid}) => `/stream/${spk}/${mfid}`,
  },
  editMedia: {
    title: "Edit Media",
    re: /\/stream\/(?<spk>\d+)\/(?<mfid>\d+)\/edit/,
    route: "/stream/:spk/:mfid/edit",
    url: ({spk, mfid}) => `/stream/${spk}/${mfid}/edit`,
  },
  inspectMedia: {
    title: "Inspect MP4 file",
    re: /\/media\/inspect/,
    route: "/media/inspect",
    url: () => `/media/inspect`,
  },
  checkMediaChanges: {
    title: "Edit Media",
    re: /\/stream\/(?<spk>\d+)\/(?<mfid>\d+)\/validate/,
    route: "/stream/:spk/:mfid/validate",
    url: ({spk, mfid}) => `/stream/${spk}/${mfid}/validate`,
  },
  deleteMedia: {
    title: "Delete Media",
    re: /\/stream\/(?<spk>\d+)\/(?<mfid>\d+)\/delete/,
    route: "/stream/:spk/:mfid/delete",
    url: ({spk, mfid}) => `/stream/${spk}/${mfid}/delete`,
  },
  listStreams: {
    title: "Available DASH streams",
    re: /\/streams/,
    route: "/streams",
    url: () => `/streams`,
  },
  time: {
    title: "Current time of day",
    re: /\/time\/(?<method>(head|xsd|iso|http-ntp))/,
    route: "/time/:method",
    url: ({method}) => `/time/${method}`,
  },
  deleteStream: {
    title: "Delete stream",
    re: /\/stream\/(?<spk>\d+)\/delete/,
    route: "/stream/:spk/delete",
    url: ({spk}) => `/stream/${spk}/delete`,
  },
  addStream: {
    title: "Add stream",
    re: /\/streams\/add/,
    route: "/streams/add",
    url: () => `/streams/add`,
  },
  viewStream: {
    title: "Edit Stream",
    re: /\/stream\/(?<spk>\d+)/,
    route: "/stream/:spk",
    url: ({spk}) => `/stream/${spk}`,
  },
  editStreamDefaults: {
    title: "Edit Stream Defaults",
    re: /\/stream\/(?<spk>\d+)\/defaults/,
    route: "/stream/:spk/defaults",
    url: ({spk}) => `/stream/${spk}/defaults`,
  },
  uploadBlob: {
    title: "Upload blob",
    re: /\/media\/(?<spk>\d+)\/blob/,
    route: "/media/:spk/blob",
    url: ({spk}) => `/media/${spk}/blob`,
  },
  video: {
    title: "DASH test stream player",
    re: /\/play\/(?<mode>(live|vod|odvod))\/(?<stream>\w+)\/(?<manifest>\w+)\/index.html/,
    route: "/play/:mode/:stream/:manifest/index.html",
    url: ({mode, stream, manifest}) => `/play/${mode}/${stream}/${manifest}/index.html`,
  },
  videoMps: {
    title: "DASH test stream player",
    re: /\/play\/mps\/(?<mode>(live|vod))\/(?<mps_name>\w+)\/(?<manifest>\w+)\/index.html/,
    route: "/play/mps/:mode/:mps_name/:manifest/index.html",
    url: ({mode, mps_name, manifest}) => `/play/mps/${mode}/${mps_name}/${manifest}/index.html`,
  },
  logout: {
    title: "Log out of site",
    re: /\/logout/,
    route: "/logout",
    url: () => `/logout`,
  },
  listManifests: {
    title: "DASH fragment",
    re: /\/api\/manifests/,
    route: "/api/manifests",
    url: () => `/api/manifests`,
  },
  mpsManifest: {
    title: "DASH multi-period manifests",
    re: /\/mps\/(?<mode>(live|vod))\/(?<mps_name>\w+)\/(?<manifest>\w+)/,
    route: "/mps/:mode/:mps_name/:manifest",
    url: ({mode, mps_name, manifest}) => `/mps/${mode}/${mps_name}/${manifest}`,
  },
  mpsBaseUrl: {
    title: "Used for generating BaseURL values",
    re: /\/mps\/(?<mode>(live|vod))\/(?<mps_name>\w+)\/(?<ppk>\d+)\//,
    route: "/mps/:mode/:mps_name/:ppk/",
    url: ({mode, mps_name, ppk}) => `/mps/${mode}/${mps_name}/${ppk}/`,
  },
  mpsInitSeg: {
    title: "Init segments for multi-period streams",
    re: /\/mps\/(?<mode>(live|vod))\/(?<mps_name>\w+)\/(?<ppk>\d+)\/(?<filename>\w+)\/init.(?<ext>(mp4|m4v|m4a|m4s))/,
    route: "/mps/:mode/:mps_name/:ppk/:filename/init.:ext",
    url: ({mode, mps_name, ppk, filename, ext}) => `/mps/${mode}/${mps_name}/${ppk}/${filename}/init.${ext}`,
  },
  mpsMediaSegByNumber: {
    title: "media segments for multi-period streams",
    re: /\/mps\/(?<mode>(live|vod))\/(?<mps_name>\w+)\/(?<ppk>\d+)\/(?<filename>\w+)\/(?<segment_num>\d+).(?<ext>(mp4|m4v|m4a|m4s))/,
    route: "/mps/:mode/:mps_name/:ppk/:filename/:segment_num.:ext",
    url: ({mode, mps_name, ppk, filename, segment_num, ext}) => `/mps/${mode}/${mps_name}/${ppk}/${filename}/${segment_num}.${ext}`,
  },
  mpsMediaSegByTime: {
    title: "media segments for multi-period streams using timelines",
    re: /\/mps\/(?<mode>(live|vod))\/(?<mps_name>\w+)\/(?<ppk>\d+)\/(?<filename>\w+)\/time\/(?<segment_time>\d+).(?<ext>(mp4|m4v|m4a|m4s))/,
    route: "/mps/:mode/:mps_name/:ppk/:filename/time/:segment_time.:ext",
    url: ({mode, mps_name, ppk, filename, segment_time, ext}) => `/mps/${mode}/${mps_name}/${ppk}/${filename}/time/${segment_time}.${ext}`,
  },
  routeMap: {
    title: "URL routing data",
    re: /\/libs\/routemap.js/,
    route: "/libs/routemap.js",
    url: () => `/libs/routemap.js`,
  },
  contentRoles: {
    title: "MPEG content roles",
    re: /\/api\/ContentRoles.json/,
    route: "/api/ContentRoles.json",
    url: () => `/api/ContentRoles.json`,
  },
  optionFieldGroups: {
    title: "options fields",
    re: /\/libs\/options.js/,
    route: "/libs/options.js",
    url: () => `/libs/options.js`,
  },
  esmWrapper: {
    title: "ESM JavaScript wrapper",
    re: /\/libs\/(?<filename>\w+)/,
    route: "/libs/:filename",
    url: ({filename}) => `/libs/${filename}`,
  },
  addMps: {
    title: "Add new multi-period stream",
    re: /\/api\/multi-period-streams\/.add/,
    route: "/api/multi-period-streams/.add",
    url: () => `/api/multi-period-streams/.add`,
  },
  cgiOptions: {
    title: "Manifest and Media CGI options",
    re: /\/api\/cgiOptions/,
    route: "/api/cgiOptions",
    url: () => `/api/cgiOptions`,
  },
  editMps: {
    title: "Edit multi-period stream",
    re: /\/api\/multi-period-streams\/(?<mps_name>\w+)/,
    route: "/api/multi-period-streams/:mps_name",
    url: ({mps_name}) => `/api/multi-period-streams/${mps_name}`,
  },
  editUser: {
    title: "Edit User",
    re: /\/api\/users\/(?<upk>\d+)/,
    route: "/api/users/:upk",
    url: ({upk}) => `/api/users/${upk}`,
  },
  listMps: {
    title: "Available DASH multi-period streams",
    re: /\/api\/multi-period-streams/,
    route: "/api/multi-period-streams",
    url: () => `/api/multi-period-streams`,
  },
  listUsers: {
    title: "List All Users",
    re: /\/api\/users/,
    route: "/api/users",
    url: () => `/api/users`,
  },
  login: {
    title: "Log into site",
    re: /\/api\/login/,
    route: "/api/login",
    url: () => `/api/login`,
  },
  refreshAccessToken: {
    title: "Refresh access token",
    re: /\/api\/refresh\/access/,
    route: "/api/refresh/access",
    url: () => `/api/refresh/access`,
  },
  refreshCsrfTokens: {
    title: "Refresh access token",
    re: /\/api\/refresh\/csrf/,
    route: "/api/refresh/csrf",
    url: () => `/api/refresh/csrf`,
  },
  validateMps: {
    title: "Check MPS settings are valid",
    re: /\/api\/multi-period-streams.validate/,
    route: "/api/multi-period-streams.validate",
    url: () => `/api/multi-period-streams.validate`,
  },
  favicon: {
    title: "favicon",
    re: /\/favicon.ico/,
    route: "/favicon.ico",
    url: () => `/favicon.ico`,
  },
  es5Home: {
    title: "DASH test streams",
    re: /\/es5\//,
    route: "/es5/",
    url: () => `/es5/`,
  },
  home: {
    title: "DASH test streams",
    re: /\//,
    route: "/",
    url: () => `/`,
  },
};

export const uiRouteMap = {
  addMps: {
    title: "add-mps",
    re: /\/multi-period-streams\/.add/,
    route: "/multi-period-streams/.add",
    url: () => `/multi-period-streams/.add`,
  },
  changePassword: {
    title: "change-password",
    re: /\/change-password/,
    route: "/change-password",
    url: () => `/change-password`,
  },
  cgiOptions: {
    title: "cgi-options",
    re: /\/options/,
    route: "/options",
    url: () => `/options`,
  },
  editMps: {
    title: "edit-mps",
    re: /\/multi-period-streams\/(?<mps_name>\w+)/,
    route: "/multi-period-streams/:mps_name",
    url: ({mps_name}) => `/multi-period-streams/${mps_name}`,
  },
  editUser: {
    title: "edit-user",
    re: /\/users\/(?<username>\w+)/,
    route: "/users/:username",
    url: ({username}) => `/users/${username}`,
  },
  home: {
    title: "home",
    re: /\//,
    route: "/",
    url: () => `/`,
  },
  listMps: {
    title: "list-mps",
    re: /\/multi-period-streams/,
    route: "/multi-period-streams",
    url: () => `/multi-period-streams`,
  },
  listUsers: {
    title: "list-users",
    re: /\/users/,
    route: "/users",
    url: () => `/users`,
  },
  login: {
    title: "login",
    re: /\/login/,
    route: "/login",
    url: () => `/login`,
  },
  validator: {
    title: "validator",
    re: /\/validate/,
    route: "/validate",
    url: () => `/validate`,
  },
};