#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import datetime
import logging

from dashlive.utils.date_time import from_isodatetime, to_iso_datetime
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
    featured=True)

AST_HTML = '''
<p>
  Specify availabilityStartTime as "today", "now", "year",
  "month", "epoch" or an ISO datetime (YYYY-MM-DDTHH:MM:SSZ).
  "today" will select midnight UTC today,
  "month" will select midnight UTC at the start of this month,
  "year" will select midnight UTC at the start of this year,
  "now" will select  publishTime - timeShiftBufferDepth, and
  "epoch" will select the Unix epoch (Jan 1 1970).
</p>
'''

SPECIAL_AST_VALUES = {'now', 'today', 'month', 'year', 'epoch'}

def ast_from_string(value: str) -> datetime.datetime | str:
    if value in SPECIAL_AST_VALUES:
        return value
    try:
        value = from_isodatetime(value)
    except ValueError as err:
        logging.warning('Failed to parse availabilityStartTime: %s', err)
        raise err
    return value

def ast_to_string(value: datetime.datetime | str | None) -> str:
    if value in SPECIAL_AST_VALUES:
        return value
    if value is None:
        return ''
    return to_iso_datetime(value)


AvailabilityStartTime = DashOption(
    usage=OptionUsage.MANIFEST + OptionUsage.VIDEO + OptionUsage.AUDIO + OptionUsage.TEXT,
    short_name='ast',
    full_name='availabilityStartTime',
    title='Availability start time',
    description='Sets availabilityStartTime for live streams',
    from_string=ast_from_string,
    to_string=ast_to_string,
    cgi_name='start',
    cgi_type='(today|month|year|epoch|now|<iso-datetime>)',
    cgi_choices=('year', 'today', 'month', 'epoch', 'now'),
    html=AST_HTML,
    input_type='textList')

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
    ))

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

Leeway = DashOption(
    usage=OptionUsage.MANIFEST + OptionUsage.VIDEO + OptionUsage.AUDIO + OptionUsage.TEXT,
    short_name='lee',
    full_name='leeway',
    title='Fragment expiration leeway',
    description='Number of seconds after a fragment has expired before it becomes unavailable',
    from_string=DashOption.int_or_none_from_string,
    cgi_name='leeway',
    input_type='numberList',
    cgi_choices=('16', '60', '0'))

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
    featured=True)

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
    cgi_type='<number>',
    input_type='numberList')

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
    featured=True)

SegmentTimeline = DashOption(
    usage=OptionUsage.MANIFEST,
    short_name='st',
    full_name='segmentTimeline',
    title='Segment timeline',
    description='Enable or disable segment timeline',
    from_string=DashOption.bool_from_string,
    to_string=DashOption.bool_to_string,
    cgi_name='timeline',
    cgi_choices=(
        ('No (use $Number$)', '0'),
        ('Yes (use $Time$)', '1')),
    featured=True)

TimeshiftBufferDepth = DashOption(
    usage=OptionUsage.MANIFEST + OptionUsage.VIDEO + OptionUsage.AUDIO + OptionUsage.TEXT,
    short_name='tbd',
    full_name='timeShiftBufferDepth',
    title='timeShiftBufferDepth size',
    description='Number of seconds for timeShiftBufferDepth',
    from_string=DashOption.int_or_none_from_string,
    cgi_name='depth',
    cgi_type='<seconds>',
    cgi_choices=('1800', '30'),
    input_type='numberList')

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
    Leeway,
    ManifestHttpError,
    MinimumUpdatePeriod,
    OperatingMode,
    Periods,
    SegmentTimeline,
    TimeshiftBufferDepth,
    UpdateCount,
    UseBaseUrl
]
