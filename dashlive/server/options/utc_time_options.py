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
    input_type='number',
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
    input_type='select',
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

NTP_POOLS: dict[str, list[str]] = {
    'europe-ntp': [
        '0.europe.pool.ntp.org', '1.europe.pool.ntp.org',
        '2.europe.pool.ntp.org', '3.europe.pool.ntp.org',
    ],
    'google': [
        'time1.google.com', 'time2.google.com',
        'time3.google.com', 'time4.google.com',
    ]
}

POOL_NAMES: list[str] = sorted(list(NTP_POOLS.keys()))

NTPSources = DashOption(
    usage=OptionUsage.MANIFEST,
    short_name='ntps',
    full_name='ntpSources',
    title='NTP time servers',
    description='List of servers to use for NTP requests',
    from_string=DashOption.list_without_none_from_string,
    to_string=lambda servers: ','.join(servers),
    input_type='select',
    cgi_name='ntp_servers',
    cgi_type=f'({"|".join(POOL_NAMES)}|<server>,..)',
    cgi_choices=tuple([None] + POOL_NAMES))

time_options = [
    ClockDrift,
    NTPSources,
    UTCMethod,
    UTCValue
]
