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
import hashlib
import logging
from typing import AbstractSet, Iterator, NamedTuple, Set

from dashlive.mpeg.dash.profiles import primary_profiles
from dashlive.server.options.drm_options import DrmLocationOption, DrmSelection
from dashlive.server.options.repository import OptionsRepository
from dashlive.server.options.types import OptionUsage
from dashlive.utils.json_object import JsonObject

DashCgiOption = tuple[str, list[str]]

class SupportedOptionTuple(NamedTuple):
    cgi_name: str
    num_options: int
    options: list[str]

    def __str__(self) -> str:
        return f'{self.cgi_name}={self.options}'


class SupportedOptionTupleList:
    __dict__ = ('options', 'mode', 'title', 'restrictions', 'num_tests', 'kwargs')

    def __init__(self, mode: str, title: str,
                 restrictions: dict[str, tuple],
                 options: list[SupportedOptionTuple], **kwargs) -> None:
        self.options = options
        self.mode = mode
        self.title = title
        self.restrictions = restrictions
        self.num_tests = SupportedOptionTupleList.num_tests(options)
        self.kwargs = kwargs

    def __str__(self) -> str:
        lines = [
            self.title,
            f'mode={self.mode}',
            f'num_tests={self.num_tests}',
        ]
        for opt in self.options:
            lines.append(str(opt))
        return '\n'.join(lines)

    @staticmethod
    def num_tests(options: list[SupportedOptionTuple]) -> int:
        count = 0
        for opt in options:
            if count:
                count *= opt.num_options
            else:
                count = opt.num_options
        return count

    def cgi_query_combinations(self) -> Iterator[str]:
        """
        Returns an interator that yields of all possible combinations of CGI query parameters
        """
        defaults = OptionsRepository.get_default_options()
        indexes = [0] * len(self.options)
        done = False
        num_options = len(self.options)
        checked: set[bytes] = set()
        while not done:
            params: dict[str, str] = {}
            allowed = True
            for opt, idx in zip(self.options, indexes):
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
                candidate.update(**self.kwargs)
                candidate.remove_unused_parameters(self.mode)
                cgi_str = candidate.generate_cgi_parameters_string()
                digest = hashlib.sha1(bytes(cgi_str, 'ascii')).digest()
                if digest not in checked:
                    checked.add(digest)
                    yield cgi_str
            idx = 0
            while idx < num_options:
                indexes[idx] += 1
                if indexes[idx] < self.options[idx][1]:
                    break
                indexes[idx] = 0
                idx += 1
            if idx == num_options:
                done = True
        logging.debug('%s total tests=%d', self.title, len(checked))


@dataclass(slots=True, frozen=True)
class DashManifest:
    name: str
    title: str
    features: set[str]
    restrictions: dict[str, tuple] | None = field(default_factory=lambda: dict())
    segment_timeline: bool = field(default=False)

    def supported_modes(self) -> list[str]:
        return self.restrictions.get('mode', primary_profiles.keys())

    def get_supported_dash_options(
            self,
            mode: str,
            simplified: bool = False,
            use: OptionUsage | None = None,
            only: AbstractSet | None = None,
            extras: list[tuple] | None = None,
            **kwargs) -> SupportedOptionTupleList:
        """
        Returns an list of support DASH options
        """
        drm_opts = self.get_drm_options(mode)
        exclude: Set[str] = {
            'abr', 'bugCompatibility', 'drmSelection',
            'leeway', 'mode', 'minimumUpdatePeriod',
        }
        exclude.update(set(kwargs.keys()))
        if simplified:
            exclude.update({
                'availabilityStartTime', 'useBaseUrls', 'playreadyVersion',
                'playreadyPiff', 'utcMethod', 'clockDrift', 'patch'})
        if mode != 'live':
            exclude.update({'clockDrift', 'minimumUpdatePeriod', 'timeShiftBufferDepth'})
        all_options = self.features.union(set(self.restrictions.keys()))
        if only is None:
            only = all_options.difference(exclude)
        else:
            # only = all_options.intersection(only)
            for item in only:
                exclude.discard(item)
        logging.debug('exclude=%s', exclude)
        logging.debug('only=%s', only)
        options: list[SupportedOptionTuple] = []
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
            options.append(SupportedOptionTuple(dash_opt.cgi_name, len(choices), choices))
        if drm_opts != {'drm=none'} and 'drm' not in exclude:
            options.append(SupportedOptionTuple('drm', len(drm_opts), list(drm_opts)))
        if extras:
            options += extras
        logging.debug(
            'options len=%d, counts=%s', len(options),
            [f'{name}={leng}' for name, leng, choices in options])
        return SupportedOptionTupleList(
            mode=mode, options=options, title=self.title, restrictions=self.restrictions, **kwargs)

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
            for loc in DrmLocationOption.cgi_choices:
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
            'name': self.name,
            'title': self.title,
            'features': self.features,
            'restrictions': self.restrictions,
        }


default_manifest = DashManifest(
    name='hand_made',
    title='Hand-made manifest',
    features={
        'abr', 'audioCodec', 'useBaseUrls', 'drmSelection', 'eventTypes',
        'mode', 'minimumUpdatePeriod', 'patch',
        'segmentTimeline', 'utcMethod'},
)

manifest_map: dict[str, DashManifest] = {
    'hand_made.mpd': default_manifest,
    'manifest_vod_aiv.mpd': DashManifest(
        name='manifest_vod_aiv',
        title='AIV on demand profile',
        features={'abr', 'useBaseUrls'},
        restrictions={
            'mode': {'odvod'},
            'drm': {'none'},
            'acodec': 'mp4a',
        },
    ),
    'manifest_a.mpd': DashManifest(
        name='manifest_a',
        title='Vendor A live profile',
        features={'abr', 'audioCodec', 'useBaseUrls', 'mode', 'minimumUpdatePeriod',
                  'segmentTimeline'},
        segment_timeline=True,
        restrictions={
            'mode': {'live', 'vod'},
            'drm': {'none'},
        },
    ),
    'manifest_b.mpd': DashManifest(
        name='manifest_b',
        title='Vendor B VOD using live profile',
        features={'abr', 'audioCodec', 'useBaseUrls', 'drmSelection'},
        restrictions={
            'mode': {'vod'},
        },
    ),
    'manifest_e.mpd': DashManifest(
        name='manifest_e',
        title='Vendor E live profile',
        features={
            'abr', 'audioCodec', 'useBaseUrls', 'drmSelection', 'mode', 'minimumUpdatePeriod',
            'utcMethod'},
        restrictions={
            'mode': {'live', 'vod'},
        },
    ),
    'manifest_h.mpd': DashManifest(
        name='manifest_h',
        title='Vendor H live profile',
        features={'abr', 'audioCodec', 'useBaseUrls', 'drmSelection', 'mode',
                  'minimumUpdatePeriod', 'utcMethod'},
        restrictions={
            'mode': {'live', 'vod'},
        },
    ),
    'manifest_i.mpd': DashManifest(
        name='manifest_i',
        title='Vendor I live profile',
        features={'abr', 'useBaseUrls', 'audioCodec', 'drmSelection', 'mode',
                  'minimumUpdatePeriod', 'utcMethod'},
        restrictions={
            'mode': {'live', 'vod'},
            'time': {'direct'},
        },
    ),
    'manifest_ef.mpd': DashManifest(
        name='manifest_ef',
        title='Vendor EF live profile',
        features={'abr', 'useBaseUrls', 'drmSelection', 'mode'},
        restrictions={
            'mode': {'live', 'vod'},
            'acodec': {'mp4a'},
        },
    ),
    'manifest_n.mpd': DashManifest(
        name='manifest_n',
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
