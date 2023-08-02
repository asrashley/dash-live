#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from .dash_option import DashOption
from .http_error import AudioHttpError

AudioCodec = DashOption(
    name='ac',
    title='Audio Codec',
    description='Filter audio adaptation sets by audio codec (AAC or E-AC3)',
    cgi_name='acodec',
    cgi_choices=('mp4a', 'ec-3'),
    hidden=False,
    usage={'manifest'})

AudioDescriptionTrack = DashOption(
    name='ad',
    title='Audio Description',
    description='Select audio AdaptationSet that will be marked as a broadcast-mix audio description track',
    cgi_type='<id>',
    cgi_name='ad_audio',
    usage={'manifest'})

MainAudioTrack = DashOption(
    name='ma',
    title='Main audio track',
    description='Select audio AdaptationSet that will be given the "main" role',
    cgi_name='main_audio',
    cgi_choices=('mp4a', 'ec-3'),
    cgi_type='(mp4a|ec3|<id>)',
    usage={'manifest'})

audio_options = [
    AudioCodec,
    AudioDescriptionTrack,
    AudioHttpError,
    MainAudioTrack
]
