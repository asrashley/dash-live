from .dash_option import DashOption

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
    name='dloc',
    title='DRM location',
    description='Location to place DRM data',
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

DrmSelection = DashOption(
    name='drm',
    title='Encryption',
    description=(
        'Comma separated list of DRM names to enable. ' +
        'Optionally each DRM name can contain a hyphen separated list of locations for the DRM data'),
    html=HTML_DESCRIPTION,
    cgi_name='drm',
    cgi_type='<drm>,.. or <drm>-<location>,..',
    cgi_choices=(None, 'all', 'clearkey', 'marlin', 'playready'),
    hidden=False)

MarlinLicenseUrl = DashOption(
    name='mlu',
    title='Marlin LA_URL',
    description='Override the Marlin S-URL field',
    cgi_name='marlin_la_url',
    cgi_type='<escaped-url>')

PlayreadyLicenseUrl = DashOption(
    name='plu',
    title='Playready LA_URL',
    description='Override the Playready LA_URL field',
    cgi_name='playready_la_url',
    cgi_type='<escaped-url>')

PlayreadyPiff = DashOption(
    name='pff',
    title='Playready PIFF',
    description='Include PIFF sample encryption data',
    cgi_name='playready_piff',
    cgi_choices=(True, False))

PlayreadyVersion = DashOption(
    name='pvn',
    title='PlayReady Version',
    description='Set the PlayReady version compatibility for this stream',
    cgi_name='playready_version',
    cgi_choices=(1.0, 2.0, 3.0, 4.0))

drm_options = [
    DrmLocation,
    DrmSelection,
    MarlinLicenseUrl,
    PlayreadyLicenseUrl,
    PlayreadyPiff,
    PlayreadyVersion,
]
