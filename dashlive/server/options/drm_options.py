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

from typing import TypeAlias

from .dash_option import DashOption
from .types import OptionUsage

HTML_DESCRIPTION = '''
<p>A comma separated list of DRMs:</p>
<ul>
  <li>all - All supported DRMs</li>
  <li>clearkey - W3C ClearKey</li>
  <li>marlin - Intertrust Marlin</li>
  <li>none - No DRM</li>
 <li>playready - Microsoft PlayReady</li>
</ul>
<p>For example: <span class="pre">drm=playready,marlin</span></p>
<p style="margin-top: 0.5em">Optionally with a hyphen separated list of locations for the DRM data:</p>
<ul>
  <li>pro - An mspr:pro element in the MPD (only applicable to PlayReady)</li>
  <li>cenc - A cenc:pssh element in the MPD</li>
  <li>moov - A PSSH box in the init segment</li>
</ul>
<p>For example: <span class="pre">drm=playready-pro-cenc,clearkey-moov</span></p>
'''

DrmLocation = DashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO | OptionUsage.TEXT),
    short_name='dloc',
    full_name='drmLocation',
    title='DRM location',
    description='Location to place DRM data',
    from_string=DashOption.list_without_none_from_string,
    cgi_name='drmloc',
    cgi_choices=(
        ('All locations', None),
        ('mspr:pro element in MPD', 'pro'),
        ('dash:cenc element in MPD', 'cenc'),
        ('PSSH in init segment', 'moov'),
        ('mspr:pro + dash:cenc in MPD', 'pro-cenc'),
        ('mspr:pro MPD + PSSH init', 'pro-moov'),
        ('dash:cenc MPD + PSSH init', 'cenc-moov'),
    ),
    hidden=False)


# TODO: get this list from dashlive.drm
ALL_DRM_TYPES: list[str] = ['clearkey', 'marlin', 'playready']

DrmSelectionTuple: TypeAlias = tuple[str, set[str]]

def _drm_selection_from_string(value: str) -> list[DrmSelectionTuple]:
    value = value.lower()
    if value.startswith('none'):
        return []
    if value.startswith('all'):
        if '-' in value:
            locations = set(value.split('-')[1:])
        else:
            locations = {'pro', 'cenc', 'moov'}
        return [(drm, locations) for drm in ALL_DRM_TYPES]
    result = []
    for item in value.split(','):
        if '-' in item:
            parts = item.split('-')
            drm = parts[0]
            locations = set(parts[1:])
        else:
            drm = item
            locations = {'pro', 'cenc', 'moov'}
        result.append((drm, locations))
    return result


def _drm_selection_to_string(value: list[DrmSelectionTuple]) -> str:
    result: list[str] = []
    for drm, locations in value:
        if locations == {'pro', 'cenc', 'moov'}:
            result.append(drm)
        else:
            parts = [drm] + sorted(list(locations))
            result.append('-'.join(parts))
    if set(result) == set(ALL_DRM_TYPES):
        return 'all'
    return ','.join(result)


DrmSelection = DashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO | OptionUsage.TEXT),
    short_name='drm',
    full_name='drmSelection',
    title='Encryption',
    description=(
        'Comma separated list of DRM names to enable. ' +
        'Optionally each DRM name can contain a hyphen separated list of locations for the DRM data'),
    html=HTML_DESCRIPTION,
    from_string=_drm_selection_from_string,
    to_string=_drm_selection_to_string,
    cgi_name='drm',
    cgi_type='<drm>,.. or <drm>-<location>,..',
    cgi_choices=(None, 'all', 'clearkey', 'marlin', 'playready'),
    hidden=False)

MarlinLicenseUrl = DashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO),
    short_name='mlu',
    full_name='marlinLicenseUrl',
    title='Marlin LA_URL',
    description='Override the Marlin S-URL field',
    from_string=DashOption.unquoted_url_or_none_from_string,
    to_string=DashOption.quoted_url_or_none_to_string,
    cgi_name='marlin_la_url',
    cgi_type='<escaped-url>')

PlayreadyLicenseUrl = DashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO),
    short_name='plu',
    full_name='playreadyLicenseUrl',
    title='Playready LA_URL',
    description='Override the Playready LA_URL field',
    from_string=DashOption.unquoted_url_or_none_from_string,
    to_string=DashOption.quoted_url_or_none_to_string,
    cgi_name='playready_la_url',
    cgi_type='<escaped-url>')

PlayreadyPiff = DashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO),
    short_name='pff',
    full_name='playreadyPiff',
    title='Playready PIFF',
    description='Include PIFF sample encryption data',
    from_string=DashOption.bool_from_string,
    cgi_name='playready_piff',
    cgi_choices=('1', '0'))

PlayreadyVersion = DashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO),
    short_name='pvn',
    full_name='playreadyVersion',
    title='PlayReady Version',
    description='Set the PlayReady version compatibility for this stream',
    from_string=DashOption.float_or_none_from_string,
    cgi_name='playready_version',
    cgi_choices=(None, '1.0', '2.0', '3.0', '4.0'))

drm_options = [
    DrmSelection,
    MarlinLicenseUrl,
    PlayreadyLicenseUrl,
    PlayreadyPiff,
    PlayreadyVersion,
]
