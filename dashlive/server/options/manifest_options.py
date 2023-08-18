#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import datetime
import logging
from typing import Union

from dashlive.utils.timezone import UTC
from dashlive.utils.date_time import from_isodatetime
from .dash_option import DashOption
from .http_error import FailureCount, ManifestHttpError
from .types import OptionUsage

AbrControl = DashOption(
    usage=OptionUsage.MANIFEST,
    short_name='ab',
    full_name='abr',
    title='Adaptive bitrate',
    description='Enable or disable adaptive bitrate',
    from_string=DashOption.bool_from_string,
    to_string=DashOption.bool_to_string,
    cgi_name='abr',
    cgi_choices=(
        ('Enabled', '1'),
        ('Disabled', '0'),
    ),
    hidden=False)

AST_HTML = '''
<p>
  Specify availabilityStartTime as "today", "now", "epoch" or an
  ISO datetime (YYYY-MM-DDTHH:MM:SSZ). "today" will
  select midnight UTC today, "now" will select
  publishTime - timeShiftBufferDepth, and "epoch" will
  select the Unix epoch (Jan 1 1970).
</p>
'''

def ast_from_string(value: str) -> Union[datetime.datetime, str]:
    if value in {'now', 'today'}:
        return value
    if value == 'epoch':
        return datetime.datetime(1970, 1, 1, 0, 0, tzinfo=UTC())
    try:
        value = from_isodatetime(value)
    except ValueError as err:
        logging.warning('Failed to parse availabilityStartTime: %s', err)
        raise err
    return value


AvailabilityStartTime = DashOption(
    usage=OptionUsage.MANIFEST + OptionUsage.VIDEO + OptionUsage.AUDIO + OptionUsage.TEXT,
    short_name='ast',
    full_name='availabilityStartTime',
    title='Availability start time',
    description='Sets availabilityStartTime for live streams',
    from_string=ast_from_string,
    to_string=DashOption.datetime_or_none_to_string,
    cgi_name='start',
    cgi_type='(today|epoch|now|<iso-datetime>)',
    cgi_choices=('today', 'epoch', 'now'),
    html=AST_HTML)

UseBaseUrl = DashOption(
    usage=OptionUsage.MANIFEST,
    short_name='base',
    full_name='useBaseUrls',
    title='Use BaseURLs',
    description='Include a BaseURL element?',
    from_string=DashOption.bool_from_string,
    to_string=DashOption.bool_to_string,
    cgi_name='base',
    cgi_choices=(
        ('Yes', '1'),
        ('No', '0')
    ),
    hidden=False)

Bugs = DashOption(
    usage=OptionUsage.MANIFEST + OptionUsage.VIDEO + OptionUsage.AUDIO + OptionUsage.TEXT,
    short_name='bug',
    full_name='bugCompatibility',
    title='Bug compatibility',
    description='Produce a stream with known bugs. The value is a comma separated list of bug names',
    from_string=DashOption.list_without_none_from_string,
    to_string=lambda bugs: ','.join(bugs),
    cgi_name='bugs',
    cgi_choices=(None, 'saio'))

OperatingMode = DashOption(
    usage=OptionUsage.MANIFEST,
    short_name='md',
    full_name='mode',
    title='Operating mode',
    description='DASH operating mode',
    cgi_name='mode',
    cgi_choices=(
        ('VOD live profile', 'vod'),
        ('Live stream', 'live'),
        ('VOD OnDemand profile', 'odvod'),
    ),
    hidden=False)

MinimumUpdatePeriod = DashOption(
    usage=OptionUsage.MANIFEST,
    short_name='mup',
    full_name='minimumUpdatePeriod',
    title='Minimum update period',
    description='Specify minimumUpdatePeriod (in seconds) or -1 to disable updates',
    from_string=DashOption.int_or_none_from_string,
    cgi_name='mup',
    cgi_choices=(
        ('Every 2 fragments', None),
        ('Never', '-1'),
        ('Every fragment', '4'),
        ('Every 30 seconds', '30'),
    ),
    cgi_type='<number>')

Periods = DashOption(
    usage=OptionUsage.MANIFEST + OptionUsage.VIDEO + OptionUsage.AUDIO + OptionUsage.TEXT,
    short_name='per',
    full_name='numPeriods',
    title='Multi-period',
    description='The number of Periods to include in the manifest',
    from_string=DashOption.int_or_none_from_string,
    cgi_name='periods',
    cgi_type='<number>',
    cgi_choices=(None, '2', '3'),
    hidden=False)

TimeshiftBufferDepth = DashOption(
    usage=OptionUsage.MANIFEST + OptionUsage.VIDEO + OptionUsage.AUDIO + OptionUsage.TEXT,
    short_name='tbd',
    full_name='timeShiftBufferDepth',
    title='timeShiftBufferDepth size',
    description='Number of seconds for timeShiftBufferDepth',
    from_string=DashOption.int_or_none_from_string,
    cgi_name='depth',
    cgi_type='<seconds>',
    cgi_choices=('1800', '30'))

UpdateCount = DashOption(
    usage=OptionUsage.MANIFEST,
    short_name='uc',
    full_name='updateCount',
    title='Manifest update count',
    description='Counter of manifest reloads',
    from_string=DashOption.int_or_none_from_string,
    cgi_name='update',
    cgi_type='<number>')

manifest_options = [
    AbrControl,
    AvailabilityStartTime,
    Bugs,
    FailureCount,
    ManifestHttpError,
    MinimumUpdatePeriod,
    OperatingMode,
    Periods,
    TimeshiftBufferDepth,
    UpdateCount,
    UseBaseUrl
]
