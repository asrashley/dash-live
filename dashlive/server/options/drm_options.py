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

from dashlive.drm.location import DrmLocation
from dashlive.drm.system import DrmSystem

from .dash_option import DashOption
from .types import OptionUsage

ClearkeyLicenseUrl = DashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO),
    short_name='clu',
    full_name='licenseUrl',
    prefix='clearkey',
    title='Clearkey LA_URL',
    description='Override the Clearkey license URL field',
    from_string=DashOption.unquoted_url_or_none_from_string,
    to_string=DashOption.quoted_url_or_none_to_string,
    cgi_name='clearkey__la_url',
    cgi_type='<escaped-url>')

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

DrmLocationOption = DashOption(
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
        ('mspr:pro + dash:cenc in MPD', 'cenc-pro'),
        ('mspr:pro MPD + PSSH init', 'moov-pro'),
        ('dash:cenc MPD + PSSH init', 'cenc-moov'),
    ),
    input_type='select',
    featured=True)


ALL_DRM_NAMES: set[str] = set(DrmSystem.values())
ALL_DRM_LOCATIONS: set[DrmLocation] = set(DrmLocation.all())

DrmSelectionTuple: TypeAlias = tuple[str, set[DrmLocation]]

def _drm_selection_from_string(value: str) -> list[DrmSelectionTuple]:
    locations: set[DrmLocation]

    value = value.lower()
    if value.startswith('none') or value == '':
        return []
    if value.startswith('all'):
        if '-' in value:
            locations = {DrmLocation.from_string(loc) for loc in value.split('-')[1:]}
        else:
            locations = ALL_DRM_LOCATIONS
        return [(drm, locations) for drm in DrmSystem.values()]
    result: list[DrmSelectionTuple] = []
    for item in value.split(','):
        if '-' in item:
            parts = item.split('-')
            drm = parts[0]
            locations = {DrmLocation(loc) for loc in parts[1:]}
        else:
            drm = item
            locations = ALL_DRM_LOCATIONS
        result.append((drm, locations))
    return result


def _drm_selection_to_string(value: list[DrmSelectionTuple]) -> str:
    result: list[str] = []
    for drm, locations in value:
        if locations == ALL_DRM_LOCATIONS:
            result.append(drm)
        else:
            parts = [drm] + sorted([loc.to_json() for loc in locations])
            result.append('-'.join(parts))
    if set(result) == ALL_DRM_NAMES:
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
    input_type='multipleSelect',
    cgi_choices=tuple([None, 'all'] + DrmSystem.values()),
    featured=True)

MarlinLicenseUrl = DashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO),
    short_name='mlu',
    full_name='licenseUrl',
    prefix='marlin',
    title='Marlin LA_URL',
    description='Override the Marlin S-URL field',
    from_string=DashOption.unquoted_url_or_none_from_string,
    to_string=DashOption.quoted_url_or_none_to_string,
    cgi_name='marlin__la_url',
    cgi_type='<escaped-url>')

PlayreadyLicenseUrl = DashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO),
    short_name='plu',
    full_name='licenseUrl',
    title='Playready LA_URL',
    description='Override the Playready LA_URL field',
    from_string=DashOption.unquoted_url_or_none_from_string,
    to_string=DashOption.quoted_url_or_none_to_string,
    cgi_name='playready__la_url',
    cgi_type='<escaped-url>',
    prefix='playready')

PlayreadyPiff = DashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO),
    short_name='pff',
    full_name='piff',
    title='Playready PIFF',
    prefix='playready',
    description='Include PIFF sample encryption data',
    from_string=DashOption.bool_from_string,
    to_string=DashOption.bool_to_string,
    input_type='checkbox',
    cgi_name='playready__piff',
    cgi_choices=('1', '0'))

PlayreadyVersion = DashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO),
    short_name='pvn',
    full_name='version',
    prefix='playready',
    title='Playready Version',
    description='Set the PlayReady version compatibility for this stream',
    from_string=DashOption.float_or_none_from_string,
    input_type='select',
    cgi_name='playready__version',
    cgi_choices=(None, '1.0', '2.0', '3.0', '4.0'))

drm_options = [
    ClearkeyLicenseUrl,
    DrmSelection,
    MarlinLicenseUrl,
    PlayreadyLicenseUrl,
    PlayreadyPiff,
    PlayreadyVersion,
]
