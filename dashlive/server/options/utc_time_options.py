#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from .dash_option import DashOption
from .types import OptionUsage

ClockDrift = DashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.TIME),
    short_name='dft',
    full_name='clockDrift',
    title='Clock drift',
    description='Number of seconds of delay to add to wall clock time',
    from_string=DashOption.int_or_none_from_string,
    cgi_name='drift',
    cgi_type='<seconds>',
    cgi_choices=(None, '10'))

UTCMethod = DashOption(
    usage=OptionUsage.MANIFEST,
    short_name='utc',
    full_name='utcMethod',
    title='UTC timing method',
    description='Select UTCTiming element method.',
    from_string=DashOption.string_or_none,
    cgi_name='time',
    cgi_choices=(None, 'direct', 'head', 'http-ntp', 'iso', 'ntp', 'sntp', 'xsd'),
    featured=True)

UTCValue = DashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.TIME),
    short_name='utv',
    full_name='utcValue',
    title='UTC value',
    description='Sets the value attribute of the UTCTiming element',
    from_string=DashOption.string_or_none,
    cgi_name='time_value',
    cgi_type='<string>')

time_options = [
    ClockDrift,
    UTCMethod,
    UTCValue
]
