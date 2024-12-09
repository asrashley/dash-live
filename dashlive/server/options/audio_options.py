#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from .dash_option import DashOption
from .http_error import AudioHttpError
from .types import OptionUsage

AudioCodec = DashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO),
    short_name='ac',
    full_name='audioCodec',
    title='Audio Codec',
    description='Filter audio adaptation sets by audio codec (AAC or E-AC3)',
    cgi_name='acodec',
    cgi_choices=(
        ('HEAAC codec', 'mp4a'),
        ('EAC3 codec', 'ec-3'),
        ('Any codec', 'any'),
    ),
    input_type='select',
    featured=True)

AudioDescriptionTrack = DashOption(
    usage=OptionUsage.MANIFEST,
    short_name='ad',
    full_name='audioDescription',
    title='Audio Description',
    description='Select audio AdaptationSet that will be marked as a broadcast-mix audio description track',
    cgi_type='<id>',
    cgi_name='ad_audio',
    input_type='audio_representation')

MainAudioTrack = DashOption(
    usage=OptionUsage.MANIFEST,
    short_name='ma',
    full_name='mainAudio',
    title='Main audio track',
    description='Select audio AdaptationSet that will be given the "main" role',
    cgi_name='main_audio',
    cgi_type='<id>',
    input_type='audio_representation')

audio_options = [
    AudioCodec,
    AudioDescriptionTrack,
    AudioHttpError,
    MainAudioTrack
]
