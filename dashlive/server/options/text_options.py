#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from .dash_option import DashOption
from .http_error import TextHttpError
from .types import OptionUsage

MainTextTrack = DashOption(
    usage=OptionUsage.MANIFEST,
    short_name='mt',
    full_name='mainText',
    title='Main text track',
    description='Select text AdaptationSet that will be given the "main" role',
    from_string=DashOption.string_or_none,
    cgi_name='main_text',
    cgi_type='(<id>)')

TextCodec = DashOption(
    usage=OptionUsage.MANIFEST,
    short_name='tc',
    full_name='textCodec',
    title='Text Codec',
    description='Filter text adaptation sets by text codec',
    from_string=DashOption.string_or_none,
    cgi_name='tcodec',
    cgi_choices=(
        ('Any codec', None),
        ('im1t codec', 'im1t|etd1'),
    ))

text_options = [
    MainTextTrack,
    TextCodec,
    TextHttpError,
]
