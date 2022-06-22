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

manifest = {
    'hand_made.mpd': {
        'title': 'Hand-made manifest',
        'modes': ['live', 'vod', 'odvod']
    },
    'manifest_vod_aiv.mpd': {
        'title': 'AIV on demand profile',
        'modes': ['odvod'],
        'params': {
            'mode': 'odvod',
            'drm': 'none',
        },
    },
    'manifest_a.mpd': {
        'title': 'Vendor A live profile',
        'modes': ['live', 'vod'],
        'params': {
            'mode': 'live',
            'drm': 'none',
        },
    },
    'vod_manifest_b.mpd': {
        'title': 'Vendor B VOD using live profile',
        'modes': ['vod'],
        'params': {
            'mode': 'live',
            'drm': 'none',
        },
    },
    'manifest_e.mpd': {
        'title': 'Vendor E live profile',
        'modes': ['live', 'vod'],
        'params': {
            'mode': 'live',
            'drm': 'none',
        },
    },
    'manifest_h.mpd': {
        'title': 'Vendor H live profile',
        'modes': ['live', 'vod'],
        'params': {
            'mode': 'live',
            'drm': 'none',
        },
    },
    'manifest_i.mpd': {
        'title': 'Vendor I live profile',
        'modes': ['live', 'vod'],
        'params': {
            'mode': 'live',
            'drm': 'none',
        },
    },
    'manifest_ef.mpd': {
        'title': 'Vendor EF live profile',
        'modes': ['live', 'vod'],
        'params': {
            'mode': 'live',
            'drm': 'none',
            'acodec': 'mp4a',
        },
    },
}
