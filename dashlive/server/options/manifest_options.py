#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import datetime
from typing import ClassVar, cast

from dashlive.utils.date_time import from_isodatetime, to_iso_datetime
from .dash_option import (
    BoolDashOption,
    CgiChoiceType,
    DashOption,
    IntOrNoneDashOption,
    StringDashOption,
    StringListDashOption,
)
from .http_error import FailureCount, ManifestHttpError
from .types import OptionUsage

AbrControl = BoolDashOption(
    usage=OptionUsage.MANIFEST,
    short_name='ab',
    full_name='abr',
    title='Adaptive bitrate',
    description='Enable or disable adaptive bitrate',
    cgi_name='abr',
    cgi_choices=(
        ('Enabled', '1'),
        ('Disabled', '0'),
    ),
    input_type='checkbox',
    featured=True)

class AvailabilityStartTimeDashOption(DashOption[datetime.datetime | str]):
    AST_HTML: ClassVar[str] = '''
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

    SPECIAL_AST_VALUES: ClassVar[set[str]] = {'now', 'today', 'month', 'year', 'epoch'}

    def __init__(self) -> None:
        super().__init__(
            usage=OptionUsage.MANIFEST + OptionUsage.VIDEO + OptionUsage.AUDIO + OptionUsage.TEXT,
            short_name='ast',
            full_name='availabilityStartTime',
            title='Availability start time',
            description='Sets availabilityStartTime for live streams',
            cgi_name='start',
            cgi_type='(today|month|year|epoch|now|<iso-datetime>)',
            cgi_choices=('year', 'today', 'month', 'epoch', 'now'),
            html=AvailabilityStartTimeDashOption.AST_HTML,
            input_type='textList'
        )

    def from_string(self, value: str) -> datetime.datetime | str:
        if value == '' and self.default is not None:
            return self.default
        if value in AvailabilityStartTimeDashOption.SPECIAL_AST_VALUES:
            return value
        return cast(datetime.datetime, from_isodatetime(value))

    def to_string(self, value: datetime.datetime | str | None) -> str:
        if value is None:
            return ''
        if value in AvailabilityStartTimeDashOption.SPECIAL_AST_VALUES:
            return cast(str, value)
        return to_iso_datetime(value)


AvailabilityStartTime = AvailabilityStartTimeDashOption()

UseBaseUrl = BoolDashOption(
    usage=OptionUsage.MANIFEST,
    short_name='base',
    full_name='useBaseUrls',
    title='Use BaseURLs',
    description='Include a BaseURL element?',
    input_type='checkbox',
    cgi_name='base',
    cgi_choices=(
        ('Yes', '1'),
        ('No', '0')
    ))

Bugs = StringListDashOption(
    usage=OptionUsage.MANIFEST + OptionUsage.VIDEO + OptionUsage.AUDIO + OptionUsage.TEXT,
    short_name='bug',
    full_name='bugCompatibility',
    title='Bug compatibility',
    description='Produce a stream with known bugs',
    cgi_name='bugs',
    cgi_choices=(None, 'saio'))

Leeway = IntOrNoneDashOption(
    usage=OptionUsage.MANIFEST + OptionUsage.VIDEO + OptionUsage.AUDIO + OptionUsage.TEXT,
    short_name='lee',
    full_name='leeway',
    title='Fragment expiration leeway',
    description='Number of seconds after a fragment has expired before it becomes unavailable',
    cgi_name='leeway',
    input_type='numberList',
    cgi_choices=('16', '60', '0'))

OperatingMode = StringDashOption(
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

MinimumUpdatePeriod = IntOrNoneDashOption(
    usage=OptionUsage.MANIFEST,
    short_name='mup',
    full_name='minimumUpdatePeriod',
    title='Minimum update period',
    description='Specify minimumUpdatePeriod (in seconds) or -1 to disable updates',
    cgi_name='mup',
    cgi_choices=(
        cast(CgiChoiceType, ('Every 2 fragments', None)),
        ('Never', '-1'),
        ('Every fragment', '4'),
        ('Every 30 seconds', '30'),
    ),
    cgi_type='<number>',
    input_type='numberList')

SegmentTimeline = BoolDashOption(
    usage=OptionUsage.MANIFEST,
    short_name='st',
    full_name='segmentTimeline',
    title='Segment timeline',
    description='Enable or disable segment timeline',
    input_type='checkbox',
    cgi_name='timeline',
    cgi_choices=(
        ('No (use $Number$)', '0'),
        ('Yes (use $Time$)', '1')),
    featured=True)

TimeshiftBufferDepth = IntOrNoneDashOption(
    usage=OptionUsage.MANIFEST + OptionUsage.VIDEO + OptionUsage.AUDIO + OptionUsage.TEXT,
    short_name='tbd',
    full_name='timeShiftBufferDepth',
    title='timeShiftBufferDepth size',
    description='Number of seconds for timeShiftBufferDepth',
    cgi_name='depth',
    cgi_type='<seconds>',
    cgi_choices=('1800', '30'),
    input_type='numberList')

UpdateCount = IntOrNoneDashOption(
    usage=OptionUsage.MANIFEST,
    short_name='uc',
    full_name='updateCount',
    title='Manifest update count',
    description='Counter of manifest reloads',
    cgi_name='update',
    cgi_type='<number>')

UsePatches = BoolDashOption(
    usage=OptionUsage.MANIFEST,
    short_name='patch',
    full_name='patch',
    title='Use MPD patches',
    description='Use MPD patches for live streams',
    input_type='checkbox',
    cgi_name='patch',
    cgi_choices=(
        ('No', '0'),
        ('Yes', '1'),
    ))

ForcePeriodDurations = BoolDashOption(
    usage=OptionUsage.MANIFEST,
    short_name='fpd',
    full_name='forcePeriodDurations',
    title='Forced Period durations',
    description='Always add a duration attribute to Period elements',
    input_type='checkbox',
    cgi_name='periodDur',
    cgi_choices=(
        ('No', '0'),
        ('Yes', '1'),
    ))

manifest_options = [
    AbrControl,
    AvailabilityStartTime,
    Bugs,
    FailureCount,
    ForcePeriodDurations,
    Leeway,
    ManifestHttpError,
    MinimumUpdatePeriod,
    OperatingMode,
    SegmentTimeline,
    TimeshiftBufferDepth,
    UpdateCount,
    UseBaseUrl,
    UsePatches,
]
