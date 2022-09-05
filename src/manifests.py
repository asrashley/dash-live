#############################################################################
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import options

class DashManifest(object):
    def __init__(self, title, features, restrictions=None):
        self.title = title
        self.features = features
        if restrictions is None:
            restrictions = {}
        self.restrictions = restrictions

    def supported_modes(self):
        return self.restrictions.get('mode', options.supported_modes)

    def get_cgi_options(self, simplified=False):
        cgi_options = []
        drmloc = []
        for opt in options.options:
            if opt.name == 'drmloc':
                for name, value in opt.options:
                    if value:
                        drmloc.append(value.split('=')[1])
        for opt in options.options:
            if opt.name not in self.features and opt.name not in self.restrictions.keys():
                continue
            # the MSE option is exluded from the list as it does not change
            # anything in the manifest responses. drmloc is handled as part
            # of the drm option
            if opt.name in {'mse', 'drmloc'}:
                continue
            if simplified and opt.name in {'abr', 'mup'}:
                continue
            if opt.name in self.restrictions:
                allowed = self.restrictions[opt.name]
                opts = ['{0}={1}'.format(opt.name, i) for i in allowed]
            else:
                opts = map(lambda o: o[1], opt.options)

            if opt.name == 'drm' and 'drm' in opts:
                for d in opt.options:
                    if d[1] == 'drm=none':
                        continue
                    for loc in drmloc:
                        if "pro" in loc and d[1] != 'drm=playready' and d[1] != 'drm=all':
                            continue
                        opts.append(d[1] + '-' + loc)
            cgi_options.append((opt.name, opts))
        return cgi_options


manifest = {
    'hand_made.mpd': DashManifest(
        title='Hand-made manifest',
        features={'abr', 'base', 'drm', 'events', 'mode', 'mup', 'time'},
    ),
    'manifest_vod_aiv.mpd': DashManifest(
        title='AIV on demand profile',
        features={'abr', 'base'},
        restrictions={
            'mode': {'odvod'},
            'drm': {'none'},
        },
    ),
    'manifest_a.mpd': DashManifest(
        title='Vendor A live profile',
        features={'abr', 'base', 'mode', 'mup'},
        restrictions={
            'mode': {'live', 'vod'},
            'drm': {'none'},
        },
    ),
    'vod_manifest_b.mpd': DashManifest(
        title='Vendor B VOD using live profile',
        features={'abr', 'base', 'drm'},
        restrictions={
            'mode': {'vod'},
        },
    ),
    'manifest_e.mpd': DashManifest(
        title='Vendor E live profile',
        features={'abr', 'base', 'drm', 'mode', 'mup', 'time'},
        restrictions={
            'mode': {'live', 'vod'},
        },
    ),
    'manifest_h.mpd': DashManifest(
        title='Vendor H live profile',
        features={'abr', 'base', 'drm', 'mode', 'mup', 'time'},
        restrictions={
            'mode': {'live', 'vod'},
        },
    ),
    'manifest_i.mpd': DashManifest(
        title='Vendor I live profile',
        features={'abr', 'base', 'drm', 'mode', 'mup', 'time'},
        restrictions={
            'mode': {'live', 'vod'},
            'time': {'direct'},
        },
    ),
    'manifest_ef.mpd': DashManifest(
        title='Vendor EF live profile',
        features={'abr', 'base', 'drm', 'mode'},
        restrictions={
            'mode': {'live', 'vod'},
            'acodec': {'mp4a'},
        },
    ),
    'manifest_n.mpd': DashManifest(
        title='Provider N live profile',
        features={'abr', 'base', 'drm', 'events', 'mode', 'mup'},
        restrictions={
            'mode': {'live', 'vod'},
        },
    ),
}
