#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from typing import TypeAlias, cast

from dashlive.drm.location import DrmLocation
from dashlive.drm.system import DrmSystem

from .dash_option import (
    BoolDashOption,
    CgiChoiceType,
    DashOption,
    FloatOrNoneDashOption,
    StringListDashOption,
    UrlOrNoneDashOption,
)
from .types import OptionUsage

ClearkeyLicenseUrl = UrlOrNoneDashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO),
    short_name='clu',
    full_name='licenseUrl',
    prefix='clearkey',
    title='Clearkey LA_URL',
    description='Override the Clearkey license URL field',
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

DrmLocationOption = StringListDashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO | OptionUsage.TEXT),
    short_name='dloc',
    full_name='drmLocation',
    title='DRM location',
    description='Location to place DRM data',
    cgi_name='drmloc',
    cgi_choices=(
        cast(CgiChoiceType, ('All locations', None,)),
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

class DrmSelectionOption(DashOption[list[DrmSelectionTuple]]):
    def __init__(self) -> None:
        super().__init__(
            usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO | OptionUsage.TEXT),
            short_name='drm',
            full_name='drmSelection',
            title='Encryption',
            description=(
                'Comma separated list of DRM names to enable. ' +
                'Optionally each DRM name can contain a hyphen separated list of locations for the DRM data'),
            html=HTML_DESCRIPTION,
            cgi_name='drm',
            cgi_type='<drm>,.. or <drm>-<location>,..',
            input_type='multipleSelect',
            cgi_choices=tuple([None, 'all'] + DrmSystem.values()),
            featured=True)

    def from_string(self, value: str) -> list[DrmSelectionTuple]:
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

    def to_string(self, value: list[DrmSelectionTuple]) -> str:
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


DrmSelection = DrmSelectionOption()

MarlinLicenseUrl = UrlOrNoneDashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO),
    short_name='mlu',
    full_name='licenseUrl',
    prefix='marlin',
    title='Marlin LA_URL',
    description='Override the Marlin S-URL field',
    cgi_name='marlin__la_url',
    cgi_type='<escaped-url>')

PlayreadyLicenseUrl = UrlOrNoneDashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO),
    short_name='plu',
    full_name='licenseUrl',
    title='Playready LA_URL',
    description='Override the Playready LA_URL field',
    cgi_name='playready__la_url',
    cgi_type='<escaped-url>',
    prefix='playready')

PlayreadyPiff = BoolDashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO),
    short_name='pff',
    full_name='piff',
    title='Playready PIFF',
    prefix='playready',
    description='Include PIFF sample encryption data',
    input_type='checkbox',
    cgi_name='playready__piff',
    cgi_choices=('1', '0'))

PlayreadyVersion = FloatOrNoneDashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO),
    short_name='pvn',
    full_name='version',
    prefix='playready',
    title='Playready Version',
    description='Set the PlayReady version compatibility for this stream',
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
