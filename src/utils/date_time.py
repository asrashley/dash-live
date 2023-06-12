from __future__ import division
#############################################################################
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley

#
#############################################################################
from builtins import str
from past.builtins import basestring
from past.utils import old_div
import datetime
import math
import re
import time

from utils.timezone import UTC, FixedOffsetTimeZone

# time values are in seconds since midnight, Jan. 1, 1904, in UTC time
ISO_EPOCH = datetime.datetime(year=1904, month=1, day=1, tzinfo=UTC())

date_hacks = [
    (re.compile('Apri[^l]'), 'Apr '),
    (re.compile('Sept[^e]'), 'Sep '),
    (re.compile(r'(\w{3} \d{1,2},? \d{4})\s*-\s*(.*$)'), r'\1 \2'),
    (re.compile(r'(\w{3} \d{1,2}), (\d{4}\s*\d{1,2}:\d{2})'), r'\1 \2'),
    (re.compile(r'(\w{3})-(\d{2})$'), r'\1 \2'),
    (re.compile(r'(.+) ([PCE][SD]?T)$'), r'\1')
]

date_time_re = re.compile(r''.join([
    r'^(?P<year>\d+)-(?P<month>\d+)-(?P<day>\d+)',
    r'T(?P<hour>\d+):(?P<minute>\d+):(?P<second>[\d.]+)',
    r'(?P<tzinfo>(Z|([+-]\d+:\d+)))?$'
]))

duration_re = re.compile(r''.join([
    r'^P((?P<years>\d+)Y)?((?P<months>\d+)M)?((?P<days>\d+)D)?',
    r'T((?P<hours>\d+)[H:])?((?P<minutes>\d+)[M:])?((?P<seconds>[\d.]+)S?)?$'
]))

def from_iso_epoch(delta):
    rv = ISO_EPOCH + datetime.timedelta(seconds=delta)
    return rv

def to_iso_epoch(dt):
    delta = dt - ISO_EPOCH
    return int(delta.total_seconds())


def toIsoDateTime(value):
    """ Convert a datetime to an ISO8601 formatted dateTime string.

    :param value: the dateTime to convert
    :returns: an ISO8601 formatted string version of the dateTime
    """
    rv = value.isoformat()
    if value.tzinfo is None:
        rv += 'Z'
    else:
        # replace +00:00 timezone with Z
        rv = re.sub('[+-]00:00$', 'Z', rv)
    return rv

def toIsoDuration(secs):
    """ Convert a time (in seconds) to an ISO8601 formatted duration string.

     :param secs: the duration to convert, in seconds
     :returns: an ISO8601 formatted string version of the duration
    """
    if isinstance(secs, basestring):
        secs = float(secs)
    elif isinstance(secs, datetime.timedelta):
        secs = secs.total_seconds()
    milli_secs = int((secs - math.floor(secs)) * 1000 + 0.5)
    secs = int(math.floor(secs))
    hrs = math.floor(old_div(secs, 3600))
    rv = ['PT']
    secs %= 3600
    mins = math.floor(old_div(secs, 60))
    secs %= 60
    if hrs:
        rv.append('%dH' % hrs)
    if hrs or mins:
        rv.append('%dM' % mins)
    rv.append('%d' % secs)
    if milli_secs > 0:
        ms = '%03d' % milli_secs
        while ms and ms[-1] == '0':
            ms = ms[:-1]
        rv.append('.')
        rv.append(ms)
    rv.append('S')
    return ''.join(rv)


def parse_date(date, format=None):
    """Try to create a datetime from the given string"""
    formats = ["%Y-%m-%d", "%m/%d/%y", "%m/%d/%Y", "%b %Y", "%b %y",
               "%m/xx/%y", "%a %b %d %Y", "%B %d %Y %H:%M",
               "%b %d %Y %H:%M", "%B %d %Y", "%b %d %Y",
               "%a %b %d, %Y"]
    if format is not None:
        formats.insert(0, format)
    if not isinstance(date, basestring):
        date = str(date)
    d = date
    tz = datetime.timedelta(0)
    if re.match(r'.+\s+ES?T$', date):
        tz = datetime.timedelta(hours=5)
    elif re.match(r'.+\s+EDT$', date):
        tz = datetime.timedelta(hours=4)
    elif re.match(r'.+\s+PS?T$', date):
        tz = datetime.timedelta(hours=8)
    elif re.match(r'.+\s+PDT$', date):
        tz = datetime.timedelta(hours=7)
    for regex, sub in date_hacks:
        d = regex.sub(sub, d)
    for f in formats:
        try:
            rv = datetime.datetime.strptime(d, f)
            rv += tz
            return rv
        except ValueError:
            pass
    try:
        return time.strptime(date)
    except ValueError:
        pass
    return None


def parse_timezone(value):
    if value is None:
        return None
    if value.upper() == 'Z':
        return UTC()
    return FixedOffsetTimeZone(value)

def from_isodatetime(date_time):
    """
    Convert an ISO formated date string to a datetime.datetime or datetime.timedelta
    """
    if not date_time:
        return None
    if date_time[0] == 'P':
        match = duration_re.match(date_time)
        if not match:
            raise ValueError(date_time)
        years = match.group('years')
        months = match.group('months')
        days = match.group('days')
        hours = match.group('hours')
        minutes = match.group('minutes')
        seconds = match.group('seconds')
        secs = 0
        if years is not None:
            secs += int(match.group('years')) * 3600 * 24 * 365
        if months is not None:
            secs += int(match.group('months')) * 3600 * 24 * 30
        if days is not None:
            secs += int(match.group('days')) * 3600 * 24
        if hours is not None:
            secs += int(match.group('hours')) * 3600
        if minutes is not None:
            secs += int(match.group('minutes')) * 60
        if seconds is not None:
            secs += float(match.group('seconds'))
        return datetime.timedelta(seconds=secs)
    if 'T' in date_time:
        match = date_time_re.match(date_time)
        if not match:
            raise ValueError(date_time)
        kwargs = {}
        for key, value in match.groupdict().items():
            if key == 'tzinfo':
                kwargs[key] = parse_timezone(value)
            elif key == 'second':
                if '.' in value:
                    secs = float(value)
                    kwargs[key] = int(secs)
                    secs -= int(secs)
                    kwargs['microsecond'] = int(1000000.0 * secs)
                else:
                    kwargs[key] = int(value, 10)
            else:
                kwargs[key] = int(value, 10)
        return datetime.datetime(**kwargs)
    if 'Z' not in date_time:
        try:
            return datetime.datetime.strptime(date_time, "%Y-%m-%d")
        except ValueError:
            return datetime.datetime.strptime(date_time, "%d/%m/%Y")
    return datetime.datetime.strptime(
        date_time, "%H:%M:%SZ").replace(tzinfo=UTC()).time()

def DateTimeField(value):
    """
    Used for in OBJECT_FIELDS for a datetime or timedelta
    field.
    """
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, basestring):
        return from_isodatetime(value)
    return datetime.datetime(value)

def scale_timedelta(delta, num, denom):
    """Scale the given timedelta, avoiding overflows"""
    secs = num * delta.seconds
    msecs = num * delta.microseconds
    secs += msecs / 1000000.0
    return old_div(secs, denom)
