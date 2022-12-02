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

import base64
import datetime
import decimal
import io
import json
import math
import os
import re
import time

class Buffer(object):
    def __init__(self, pos, data):
        self.pos = pos
        self.buf = data
        self.data = memoryview(self.buf)
        self.size = len(data)
        self.timestamp = time.time()

    @property
    def end(self):
        return self.pos + self.size


class BufferedReader(io.RawIOBase):
    def __init__(self, reader, buffersize=16384, data=None, offset=0,
                 size=None, max_buffers=30):
        super(BufferedReader, self).__init__()
        # print('BufferedReader', reader, buffersize, offset, size)
        self.reader = reader
        self.buffers = {}
        self.buffersize = buffersize
        self.pos = 0
        self.offset = offset
        self.size = size
        self.max_buffers = max_buffers
        self.num_buffers = 0
        if data is not None:
            self.size = len(data)
            self.buffersize = self.size
            self.buffers[0] = Buffer(self.pos, data)
            self.num_buffers = 1
            self.max_buffers = self.num_buffers + 1

    def readable(self):
        return not self.closed

    def seek(self, offset, whence=io.SEEK_SET):
        # print('seek', offset, whence)
        if whence == io.SEEK_SET:
            self.pos = offset
        elif whence == io.SEEK_CUR:
            self.pos += offset
        elif whence == io.SEEK_END:
            if self.size is None:
                self.reader.seek(0, io.SEEK_END)
                self.size = self.reader.tell() - self.offset
            self.pos = self.size + offset
        self.pos = max(0, self.pos)
        if self.size is not None:
            self.pos = min(self.pos, self.size)
        return self.pos

    def tell(self):
        return self.pos

    def seekable(self):
        return not self.closed

    def peek(self, size):
        # print('peek', self.pos, size)
        assert size > 0
        if self.size is not None:
            size = min(size, self.size - self.pos)
            if size <= 0:
                return r''
        bucket = self.pos // self.buffersize
        end = (self.pos + size) // self.buffersize
        bucket *= self.buffersize
        end *= self.buffersize
        offset = self.pos - bucket
        rv = []
        todo = size
        while todo:
            self.cache(bucket)
            sz = min(todo, self.buffersize - offset)
            rv.append(self.buffers[bucket].data[offset:].tobytes())
            bucket += self.buffersize
            offset = 0
            todo -= sz
        if len(rv) == 1:
            return rv[0]
        return r''.join(rv)

    def cache(self, bucket):
        # print('cache', bucket)
        if bucket in self.buffers:
            return
        if self.num_buffers == self.max_buffers:
            remove = None
            oldest = None
            for k, v in self.buffers.iteritems():
                if remove is None or v.timestamp < oldest:
                    remove = k
                    oldest = v.timestamp
            if remove is not None:
                del self.buffers[remove]
                self.num_buffers -= 1
        if self.reader.tell() != (bucket + self.offset):
            self.reader.seek(bucket + self.offset, io.SEEK_SET)
        b = Buffer(bucket, self.reader.read(self.buffersize))
        if self.size is None and b.size < self.buffersize:
            self.size = bucket + b.size
        self.buffers[bucket] = b
        self.num_buffers += 1
        assert self.num_buffers <= self.max_buffers

    def read(self, n=-1):
        # print('read', self.pos, n)
        if n == -1:
            return self.readall()
        if self.size is not None:
            n = min(n, self.size - self.pos)
            if n <= 0:
                return r''
        b = self.peek(n)
        self.pos += n
        return b[:n]

    def readall(self):
        self.reader.seek(self.pos)
        rv = self.reader.read()
        self.pos += len(rv)
        return rv

# A UTC class, see https://docs.python.org/2.7/library/datetime.html#datetime.tzinfo
class UTC(datetime.tzinfo):
    """UTC"""
    ZERO = datetime.timedelta(0)

    def utcoffset(self, dt):
        return self.ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return self.ZERO

def dateTimeToUnixEpoch(dt):
    """ Convert a dateTime to number of seconds since the Unix epoch.
    """
    epoch = datetime.datetime(year=1970, month=1, day=1, tzinfo=UTC())
    return (dt - epoch).total_seconds()

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
    hrs = math.floor(secs / 3600)
    rv = ['PT']
    secs %= 3600
    mins = math.floor(secs / 60)
    secs %= 60
    if hrs:
        rv.append('%dH' % hrs)
    if hrs or mins:
        rv.append('%dM' % mins)
    rv.append('%0.2fS' % secs)
    return ''.join(rv)


date_hacks = [
    (re.compile('Apri[^l]'), 'Apr '),
    (re.compile('Sept[^e]'), 'Sep '),
    (re.compile(r'(\w{3} \d{1,2},? \d{4})\s*-\s*(.*$)'), r'\1 \2'),
    (re.compile(r'(\w{3} \d{1,2}), (\d{4}\s*\d{1,2}:\d{2})'), r'\1 \2'),
    (re.compile(r'(\w{3})-(\d{2})$'), r'\1 \2'),
    (re.compile(r'(.+) ([PCE][SD]?T)$'), r'\1')
]

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

def dateTimeFormat(value, fmt):
    """ Format a date using the given format"""
    if not value:
        return value
    if isinstance(value, basestring):
        value = parse_date(value)
    if value is None:
        return value
    return value.strftime(fmt)


duration_re = re.compile(r''.join([
    r'^P((?P<years>\d+)Y)?((?P<months>\d+)M)?((?P<days>\d+)D)?',
    r'T((?P<hours>\d+)[H:])?((?P<minutes>\d+)[M:])?((?P<seconds>[\d.]+)S?)?$'
]))

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
        try:
            return datetime.datetime.strptime(
                date_time, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC())
        except ValueError:
            pass
        try:
            return datetime.datetime.strptime(
                date_time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC())
        except ValueError:
            return datetime.datetime.strptime(
                date_time, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC())
    if 'Z' not in date_time:
        try:
            return datetime.datetime.strptime(date_time, "%Y-%m-%d")
        except ValueError:
            return datetime.datetime.strptime(date_time, "%d/%m/%Y")
    return datetime.datetime.strptime(
        date_time, "%H:%M:%SZ").replace(tzinfo=UTC()).time()

def toHtmlString(item, className=None):
    """
    Converts an object in to a form suitable for rendering in an HTML page.
    """
    rv = item
    if isinstance(item, dict):
        if className:
            rv = '<table class="%s">' % className
        else:
            rv = '<table>'
        for key, val in item.iteritems():
            rv.append('<tr><td>%s</td><td>%s</td></tr>' % (
                str(key), toHtmlString(val)))
        rv.append('</table>')
        rv = '\n'.join(rv)
    elif isinstance(item, (list, tuple)):
        rv = []
        for val in item:
            rv.append(toHtmlString(val))
        if item.__class__ == tuple:
            rv = ''.join(['(', ','.join(rv), ')'])
        else:
            rv = ''.join(['[', ','.join(rv), ']'])
        if className:
            rv = '<span class="{0}">{1}</span>'.format(className, rv)
    elif isinstance(item, bool):
        if className is None:
            className = ''
        yn = "bool-yes" if item else "bool-no"
        rv = '<span class="{0} {1}">&check;</span>'.format(yn, className)
    else:
        if className:
            rv = '<span class="{0}">{1:s}</span>'.format(className, rv)
        else:
            rv = str(rv)
    return rv

def flatten(items, convert_numbers=False):
    """
    Converts an object in to a form suitable for storage.
    flatten will take a dictionary, list or tuple and inspect each item
    in the object looking for items such as datetime.datetime objects
    that need to be converted to a canonical form before
    they can be processed for storage.
    """
    if isinstance(items, dict):
        rv = {}
    else:
        rv = []
    for item in items:
        key = None
        if isinstance(items, dict):
            key = item
            item = items[key]
        if hasattr(item, 'toJSON'):
            item = item.toJSON(pure=True)
        elif isinstance(item, (datetime.date, datetime.datetime, datetime.time)):
            item = toIsoDateTime(item)
        elif isinstance(item, (datetime.timedelta)):
            item = toIsoDuration(item)
        elif convert_numbers and isinstance(item, long):
            item = '%d' % item
        elif isinstance(item, decimal.Decimal):
            item = float(item)
        elif isinstance(item, basestring):
            item = str(item).replace("'", "\'")
        elif isinstance(item, (list, set, tuple)):
            item = flatten(list(item))
        elif isinstance(item, dict):
            item = flatten(item)
        if callable(item):
            continue
        if key:
            rv[key] = item
        else:
            rv.append(item)
    if items.__class__ == tuple:
        return tuple(rv)
    return rv


def as_python(value):
    """
    Convert the value into a string of Python code.
    The result is suitable for use with eval()
    """
    if value is None:
        return 'None'
    wrap_strings = True
    if hasattr(value, 'toJSON'):
        value = value.toJSON()
        wrap_strings = False
    if isinstance(value, (list, tuple)):
        items = map(lambda v: as_python(v), list(value))
        try:
            value = '[{0}]'.format(','.join(items))
        except TypeError:
            print items
            raise
    elif isinstance(value, (dict)):
        items = []
        clz = value.get('_type', None)
        for k, v in value.iteritems():
            if k == '_type':
                continue
            if clz is None:
                items.append('"{0}": {1}'.format(k, as_python(v)))
            else:
                items.append('{0}={1}'.format(k, as_python(v)))
        if clz is None:
            value = '{' + ','.join(items) + '}'
        else:
            value = '{0}({1})'.format(clz, ','.join(items))
    elif wrap_strings and isinstance(value, (basestring)):
        if '"' in value:
            value = ''.join(["'", value, "'"])
        else:
            value = ''.join(['"', value, '"'])
    elif isinstance(value, (datetime.date, datetime.datetime, datetime.time)):
        value = 'utils.from_isodatetime("%s")' % (toIsoDateTime(value))
    elif isinstance(value, (datetime.timedelta)):
        value = 'utils.from_isodatetime("%s")' % (toIsoDuration(value))
    elif isinstance(value, decimal.Decimal):
        value = 'decimal.Decimal(%s)' % (value)
    else:
        value = str(value)
    return value


def toJson(value, indent=0):
    if not value:
        return value
    try:
        if isinstance(value, (dict, list)):
            value = flatten(value)
        return json.dumps(value, indent=indent)
    except ValueError:
        return value

def xmlSafe(value):
    """
    Convert the given string to a format that is safe for inclusion
    in an XML document.
    """
    return value.replace('&', '&amp;')

def default(value, default_value):
    if value:
        return value
    return default_value

def scale_timedelta(delta, num, denom):
    """Scale the given timedelta, avoiding overflows"""
    secs = num * delta.seconds
    msecs = num * delta.microseconds
    secs += msecs / 1000000.0
    return secs / denom

def toBase64(value):
    return base64.b64encode(value)

def toUuid(value):
    if not isinstance(value, basestring):
        value = value.encode('hex')
    value = value.upper()
    return '-'.join([
        value[:8], value[8:12], value[12:16], value[16:20],
        value[20:]])

def sizeFormat(value, binary=True):
    units = ['G', 'M', 'K', '']
    mult = 1024 if binary else 1000
    while value > mult and units:
        units.pop()
        value = value // mult
    if not units:
        units = 'T'
    return '{:d}{}B'.format(value, units[-1])

def pick_items(src, keys):
    """
    Create a new dictionary, copying all keys listed in 'keys'
    """
    rv = {}
    for key in keys:
        try:
            rv[key] = src[key]
        except KeyError:
            pass
    return rv

def dict_to_cgi_params(params):
    """
    Convert dictionary into a CGI parameter string
    """
    if not params:
        return ''
    lst = []
    for k, v in params.iteritems():
        lst.append('%s=%s' % (k, v))
    return '?' + '&'.join(lst)

#
# The following code is from djangoappengine/utils.py
#
try:
    from google.appengine.api import apiproxy_stub_map

    have_appserver = bool(apiproxy_stub_map.apiproxy.GetStub('datastore_v3'))
    on_production_server = have_appserver and not os.environ.get('SERVER_SOFTWARE', '').lower().startswith('devel')
except ImportError:
    pass
