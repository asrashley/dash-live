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

TextLanguage = DashOption(
    usage=OptionUsage.MANIFEST,
    short_name='tl',
    full_name='textLanguage',
    title='Text Language',
    description='Filter text adaptation sets by language',
    from_string=DashOption.string_or_none,
    cgi_name='tlang')

MainTextTrack = DashOption(
    usage=OptionUsage.MANIFEST,
    short_name='mt',
    full_name='mainText',
    title='Main text track',
    description='Select text AdaptationSet that will be given the "main" role',
    from_string=DashOption.string_or_none,
    cgi_name='main_text',
    cgi_type='(<id>)',
    input_type='text_representation')

text_options = [
    TextCodec,
    TextHttpError,
    TextLanguage,
    MainTextTrack
]
