#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from .dash_option import DashOption

from .event_options import EventSelection
from .http_error import FailureCount, ManifestHttpError

AbrControl = DashOption(
    name='ab',
    title='Adaptive bitrate',
    description='Enable or disable adaptive bitrate',
    cgi_name='abr',
    cgi_choices=[True, False],
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

AvailabilityStartTime = DashOption(
    name='ast',
    title='Availability start time',
    description='Sets availabilityStartTime for live streams',
    cgi_name='start',
    cgi_type='(today|epoch|now|<iso-datetime>)',
    html=AST_HTML)

UseBaseUrl = DashOption(
    name='base',
    title='Use BaseURLs',
    description='Include a BaseURL element?',
    cgi_name='base',
    cgi_choices=[True, False],
    hidden=False)

Bugs = DashOption(
    name='bug',
    title='Bug compatibility',
    description='Produce a stream with known bugs. The value is a comma separated list of bug names',
    cgi_name='bugs',
    cgi_choices=['saio'])

OperatingMode = DashOption(
    name='md',
    title='Operating mode',
    description='DASH operating mode',
    cgi_name='mode',
    cgi_choices={
        ('VOD live profile', 'vod'),
        ('Live stream', 'live'),
        ('VOD OnDemand profile', 'odvod'),
    },
    hidden=False)

MSE_HTML = '''
<p>Only relevant when using the Video Player page.</p>
<ol>
  <li> 0 - use native &lt;video&gt; element playback</li>
  <li> 1 - use MSE with EME support</li>
  <li> 2 - use MSE without EME support</li>
</ol>
'''

MediaSource = DashOption(
    name='mse',
    title='Native playback',
    description='Media Source Extension control',
    cgi_name='mse',
    cgi_choices=[
        ('Yes', 0),
        ('Use MSE/EME', 1),
        ('Use MSE (no DRM)', 2),
    ],
    html=MSE_HTML,
    hidden=False)

MinimumUpdatePeriod = DashOption(
    name='mup',
    title='Minimum update period',
    description='Specify minimumUpdatePeriod (in seconds) or -1 to disable updates',
    cgi_name='mup',
    cgi_choices={
        ('Every 2 fragments', ''),
        ('Never', '-1'),
        ('Every fragment', '4'),
        ('Every 30 seconds', '30'),
    },
    cgi_type='<number>')

Periods = DashOption(
    name='per',
    title='Multi-period',
    description='The number of Periods to include in the manifest',
    cgi_name='periods',
    cgi_type='<number>',
    cgi_choices=[None, '2', '3'],
    hidden=False)

TimeshiftBufferDepth = DashOption(
    name='tbd',
    title='timeshiftBufferDepth size',
    description='Number of seconds for timeshiftBufferDepth',
    cgi_name='depth',
    cgi_type='<seconds>')

manifest_options = [
    AbrControl,
    AvailabilityStartTime,
    Bugs,
    EventSelection,
    FailureCount,
    ManifestHttpError,
    MediaSource,
    MinimumUpdatePeriod,
    OperatingMode,
    Periods,
    TimeshiftBufferDepth,
    UseBaseUrl
]
