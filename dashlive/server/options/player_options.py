from .dash_option import DashOption
from .types import OptionUsage

DashjsVersion = DashOption(
    usage=OptionUsage.HTML,
    short_name='djVer',
    full_name='dashjsVersion',
    title='dash.js version',
    description='dash.js DASH player version',
    cgi_name='dashjs',
    cgi_choices=(None, '4.7.1'))

PLAYBACK_HTML = '''
<p>Only relevant when using the Video Player page.</p>
<ol>
  <li> native - use native &lt;video&gt; element playback</li>
  <li> shaka - use Shaka player</li>
  <li> dashjs - use dash.js player</li>
</ol>
'''

NativePlayback = DashOption(
    usage=OptionUsage.HTML,
    short_name='vp',
    full_name='videoPlayer',
    title='Video Player',
    description='Native or MSE playback control',
    cgi_name='player',
    cgi_choices=(
        ('Native video element', 'native'),
        ('Shaka', 'shaka'),
        ('dash.js', 'dashjs'),
    ),
    html=PLAYBACK_HTML,
    featured=True)

ShakaVersion = DashOption(
    usage=OptionUsage.HTML,
    short_name='skVer',
    full_name='shakaVersion',
    title='Shaka version',
    description='Shaka DASH player version',
    cgi_name='shaka',
    cgi_choices=(None, '4.11.2', '4.3.8', '2.5.4',))

player_options = [
    DashjsVersion,
    NativePlayback,
    ShakaVersion,
]
