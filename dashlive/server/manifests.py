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

from builtins import object

from dashlive.mpeg.dash.profiles import primary_profiles
from dashlive.server.options.drm_options import DrmLocation
from dashlive.server.options.cgi_options import get_cgi_options

DashCgiOption = tuple[str, list[str]]

class DashManifest(object):
    __slots__ = ('title', 'features', 'restrictions')

    def __init__(self, title, features: set[str], restrictions=None):
        self.title = title
        self.features = features
        if restrictions is None:
            restrictions = dict()
        self.restrictions = restrictions

    def supported_modes(self) -> list[str]:
        return self.restrictions.get('mode', primary_profiles.keys())

    def get_cgi_options(self, simplified: bool = False) -> list[DashCgiOption]:
        options = []
        try:
            drmloc = self.restrictions['drm']
        except KeyError:
            drmloc = [opt[1] for opt in DrmLocation.cgi_choices]
        only = self.features.union(set(self.restrictions.keys()))
        exclude = {'mse', 'bugs', 'periods'}
        if simplified:
            exclude = exclude.union({
                'abr', 'mup', 'playready_version', 'playready_piff', 'time'})
        if drmloc == {'none'}:
            exclude.add('drm')
        for opt in get_cgi_options(only=only, exclude=exclude):
            try:
                allowed = self.restrictions[opt.name]
                opts = ['{0}={1}'.format(opt.name, i) for i in allowed]
            except KeyError:
                opts = [o[1] for o in opt.options]
            if opt.name == 'drm':
                for d in opt.options:
                    if d[1] == 'drm=none':
                        continue
                    is_playready = (d[1] == 'drm=all') or ('playready' in d[1])
                    if d[1] == 'drm=marlin-moov':
                        continue
                    for loc in drmloc:
                        if loc is None or loc == 'none':
                            opts.append(d[1])
                        elif "pro" in loc and not is_playready:
                            continue
                        else:
                            opts.append(d[1] + '-' + loc)
            options.append((opt.name, opts))
        return options

    def toJSON(self):
        return {
            'title': self.title,
            'features': self.features,
            'restrictions': self.restrictions,
        }


manifest = {
    'hand_made.mpd': DashManifest(
        title='Hand-made manifest',
        features={'abr', 'base', 'drm', 'events', 'mode', 'mup', 'periods', 'time'},
    ),
    'manifest_vod_aiv.mpd': DashManifest(
        title='AIV on demand profile',
        features={'abr', 'base', 'periods'},
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
