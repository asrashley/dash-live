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

from dataclasses import dataclass, field
import logging
from typing import AbstractSet

from dashlive.mpeg.dash.profiles import primary_profiles
from dashlive.server.options.drm_options import DrmLocation, DrmSelection
from dashlive.server.options.repository import OptionsRepository
from dashlive.server.options.types import OptionUsage
from dashlive.utils.json_object import JsonObject

DashCgiOption = tuple[str, list[str]]

@dataclass(slots=True, frozen=True)
class DashManifest:
    title: str
    features: set[str]
    restrictions: dict[str, tuple] | None = field(default_factory=lambda: dict())
    segment_timeline: bool = field(default=False)

    def supported_modes(self) -> list[str]:
        return self.restrictions.get('mode', primary_profiles.keys())

    def get_cgi_query_combinations(
            self,
            mode: str,
            simplified: bool = False,
            use: OptionUsage | None = None,
            only: AbstractSet | None = None,
            extras: list[tuple] | None = None) -> list[str]:
        """
        Returns a list of all possible combinations of CGI query parameters
        """
        defaults = OptionsRepository.get_default_options()
        drm_opts = self.get_drm_options(mode)
        exclude = {'abr', 'bugCompatibility', 'drmSelection',
                   'mode', 'numPeriods', 'minimumUpdatePeriod'}
        if simplified:
            exclude = exclude.union({
                'useBaseUrls', 'playreadyVersion',
                'playreadyPiff', 'utcMethod', 'clockDrift'})
        if mode != 'live':
            exclude.add('minimumUpdatePeriod')
        all_options = self.features.union(set(self.restrictions.keys()))
        if only is None:
            only = all_options
        else:
            # only = all_options.intersection(only)
            exclude.discard(only)
        logging.debug('exclude=%s', exclude)
        logging.debug('only=%s', only)
        queries: set[str] = set()
        options: list[tuple] = []
        if use is None:
            use = ~OptionUsage.HTML
        for dash_opt in OptionsRepository.get_dash_options(only=only, exclude=exclude, use=use):
            choices: list[str] = []
            for choice in dash_opt.cgi_choices:
                if isinstance(choice, tuple):
                    value = choice[1]
                else:
                    value = choice
                if value in {None, '', 'none'}:
                    continue
                choices.append(value)
            options.append((dash_opt.cgi_name, len(choices), choices))
        if drm_opts != {'drm=none'} and 'drm' not in exclude:
            options.append(('drm', len(drm_opts), list(drm_opts)))
        if extras:
            options += extras
        logging.debug(
            'options len=%d, counts=%s', len(options),
            [f'{name}={leng}' for name, leng, choices in options])
        indexes = [0] * len(options)
        done = False
        while not done:
            params: dict[str, str] = {}
            allowed = True
            for opt, idx in zip(options, indexes):
                name, length, param_options = opt
                val = param_options[idx]
                try:
                    allowed = val in self.restrictions[name]
                except KeyError:
                    pass
                if not allowed:
                    break
                params[name] = val
            if allowed:
                candidate = OptionsRepository.convert_cgi_options(params, defaults)
                candidate.remove_unused_parameters(mode)
                queries.add(candidate.generate_cgi_parameters_string())
            idx = 0
            while idx < len(options):
                indexes[idx] += 1
                if indexes[idx] < options[idx][1]:
                    break
                indexes[idx] = 0
                idx += 1
            if idx == len(options):
                done = True
        result = list(queries)
        result.sort()
        logging.debug('%s total tests=%d', self.title, len(result))
        return result

    def get_drm_options(self, mode: str, only: AbstractSet | None = None) -> set[str]:
        """
        Calculates all possible DRM locations for this manifest.
        :only: optional set of DRM names, to restrict the list of DRM options
        """
        try:
            return self.restrictions['drm']
        except KeyError:
            pass
        d_opts: list[str] = []
        for opt in DrmSelection.cgi_choices:
            if opt is None:
                if only is None or 'none' in only:
                    d_opts.append('none')
                continue
            if only is not None and opt not in only:
                continue
            d_opts.append(f'{opt}')
            for loc in DrmLocation.cgi_choices:
                if loc[1] is None:
                    continue
                if mode == 'odvod' and 'moov' in loc[1]:
                    # adding PSSH boxes into on-demand profile content is not supported
                    continue
                d_opts.append(f'{opt}-{loc[1]}')
        return set(d_opts)

    def toJSON(self, pure: bool = False,
               exclude: AbstractSet | None = None) -> JsonObject:
        return {
            'title': self.title,
            'features': self.features,
            'restrictions': self.restrictions,
        }


manifest = {
    'hand_made.mpd': DashManifest(
        title='Hand-made manifest',
        features={
            'abr', 'audioCodec', 'useBaseUrls', 'drmSelection', 'eventTypes', 'mode',
            'minimumUpdatePeriod', 'numPeriods', 'segmentTimeline', 'utcMethod'},
    ),
    'manifest_vod_aiv.mpd': DashManifest(
        title='AIV on demand profile',
        features={'abr', 'useBaseUrls', 'numPeriods'},
        restrictions={
            'mode': {'odvod'},
            'drm': {'none'},
            'acodec': 'mp4a',
        },
    ),
    'manifest_a.mpd': DashManifest(
        title='Vendor A live profile',
        features={'abr', 'audioCodec', 'useBaseUrls', 'mode', 'minimumUpdatePeriod',
                  'segmentTimeline'},
        segment_timeline=True,
        restrictions={
            'mode': {'live', 'vod'},
            'drm': {'none'},
        },
    ),
    'vod_manifest_b.mpd': DashManifest(
        title='Vendor B VOD using live profile',
        features={'abr', 'audioCodec', 'useBaseUrls', 'drmSelection'},
        restrictions={
            'mode': {'vod'},
        },
    ),
    'manifest_e.mpd': DashManifest(
        title='Vendor E live profile',
        features={
            'abr', 'audioCodec', 'useBaseUrls', 'drmSelection', 'mode', 'minimumUpdatePeriod',
            'utcMethod'},
        restrictions={
            'mode': {'live', 'vod'},
        },
    ),
    'manifest_h.mpd': DashManifest(
        title='Vendor H live profile',
        features={'abr', 'audioCodec', 'useBaseUrls', 'drmSelection', 'mode',
                  'minimumUpdatePeriod', 'utcMethod'},
        restrictions={
            'mode': {'live', 'vod'},
        },
    ),
    'manifest_i.mpd': DashManifest(
        title='Vendor I live profile',
        features={'abr', 'useBaseUrls', 'audioCodec', 'drmSelection', 'mode',
                  'minimumUpdatePeriod', 'utcMethod'},
        restrictions={
            'mode': {'live', 'vod'},
            'time': {'direct'},
        },
    ),
    'manifest_ef.mpd': DashManifest(
        title='Vendor EF live profile',
        features={'abr', 'useBaseUrls', 'drmSelection', 'mode'},
        restrictions={
            'mode': {'live', 'vod'},
            'acodec': {'mp4a'},
        },
    ),
    'manifest_n.mpd': DashManifest(
        title='Provider N live profile',
        features={'abr', 'audioCodec', 'useBaseUrls', 'drmSelection', 'eventTypes',
                  'mode', 'minimumUpdatePeriod', 'segmentTimeline'},
        segment_timeline=True,
        restrictions={
            'mode': {'live', 'vod'},
            'timeline': {'1'},
        },
    ),
}
