#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from typing import cast
from .dash_option import CgiChoiceType, StringOrNoneDashOption
from .http_error import TextHttpError
from .types import OptionUsage

TextCodec = StringOrNoneDashOption(
    usage=OptionUsage.MANIFEST,
    short_name='tc',
    full_name='textCodec',
    title='Text Codec',
    description='Filter text adaptation sets by text codec',
    cgi_name='tcodec',
    cgi_choices=(
        cast(CgiChoiceType, ('Any codec', None)),
        ('im1t codec', 'im1t|etd1'),
    ))

TextLanguage = StringOrNoneDashOption(
    usage=OptionUsage.MANIFEST,
    short_name='tl',
    full_name='textLanguage',
    title='Text Language',
    description='Filter text adaptation sets by language',
    cgi_name='tlang')

MainTextTrack = StringOrNoneDashOption(
    usage=OptionUsage.MANIFEST,
    short_name='mt',
    full_name='mainText',
    title='Main text track',
    description='Select text AdaptationSet that will be given the "main" role',
    cgi_name='main_text',
    cgi_type='(<id>)',
    input_type='text_representation')

text_options = [
    TextCodec,
    TextHttpError,
    TextLanguage,
    MainTextTrack
]
