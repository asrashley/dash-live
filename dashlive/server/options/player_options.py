from .dash_option import DashOption
from .types import OptionUsage

DashjsVersion = DashOption(
    usage=OptionUsage.HTML,
    short_name='djVer',
    full_name='dashjsVersion',
    title='dash.js version',
    description='dash.js DASH player version',
    cgi_name='dashjs',
    cgi_choices=(None, '4.7.4', '4.7.1'),
    input_type='datalist')

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
        ('dash.js', 'dashjs'),
        ('Shaka', 'shaka'),
    ),
    html=PLAYBACK_HTML,
    input_type='select',
    featured=True)

ShakaVersion = DashOption(
    usage=OptionUsage.HTML,
    short_name='skVer',
    full_name='shakaVersion',
    title='Shaka version',
    description='Shaka DASH player version',
    cgi_name='shaka',
    cgi_choices=(None, '4.11.2', '4.3.8', '2.5.4',),
    input_type='datalist')

TextLanguage = DashOption(
    usage=OptionUsage.HTML,
    featured=True,
    short_name='ptxLang',
    full_name='textPreference',
    title='Text preference',
    description='preferred language for text tracks',
    cgi_name='text_pref',
    cgi_choices=(None, 'eng', 'cym', 'deu', 'fra', 'gla', 'gle', 'gre', 'pol', 'spa'),
    input_type='datalist')

player_options: list[DashOption] = [
    DashjsVersion,
    NativePlayback,
    ShakaVersion,
    TextLanguage,
]
