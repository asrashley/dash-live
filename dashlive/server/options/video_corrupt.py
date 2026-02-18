#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from .dash_option import IntOrNoneDashOption, StringListDashOption
from .types import OptionUsage

VideoCorruption = StringListDashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.VIDEO),
    short_name='vcor',
    full_name='videoCorruption',
    title='Video corruption',
    description=(
        'Cause video corruption to be generated when requesting a fragment at the given time. ' +
        'Invalid data is placed inside NAL packets of video frames. ' +
        'Each time must be in the form HH:MM:SSZ.'),
    cgi_name='vcorrupt',
    cgi_type='<time>,..',
    featured=False)

CorruptionFrameCount = IntOrNoneDashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.VIDEO),
    short_name='vcfc',
    full_name='videoCorruptionFrameCount',
    title='Video corruption frame count',
    description=(
        'Number of frames to corrupt per segment. ' +
        'Only relevant when the corrupt CGI parameter is present.'),
    cgi_name='frames',
    cgi_type='<number>')
