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

import base64, datetime, json, math, os, re


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
        rv = re.sub('[+-]00:00$','Z',rv)
    return rv

def toIsoDuration(secs):
    """ Convert a time (in seconds) to an ISO8601 formatted duration string.

     :param secs: the duration to convert, in seconds
     :returns: an ISO8601 formatted string version of the duration
    """
    if isinstance(secs,basestring):
        secs = float(secs)
    hrs = math.floor(secs/3600)
    rv=['PT']
    secs %= 3600
    mins = math.floor(secs/60)
    secs %= 60
    if hrs:
        rv.append('%dH'%hrs)
    if hrs or mins:
        rv.append('%dM'%mins)
    if secs:
        rv.append('%0.2fS'%secs)
    return ''.join(rv)

date_hacks = [
    (re.compile('Apri[^l]'),'Apr '), (re.compile('Sept[^e]'),'Sep '),
    (re.compile(r'(\w{3} \d{1,2},? \d{4})\s*-\s*(.*$)'), r'\1 \2' ),
    (re.compile(r'(\w{3} \d{1,2}), (\d{4}\s*\d{1,2}:\d{2})'), r'\1 \2' ),
    (re.compile(r'(\w{3})-(\d{2})$'), r'\1 \2' ),
    (re.compile(r'(.+) ([PCE][SD]?T)$'),r'\1')
]

def parse_date(date, format=None):
    """Try to create a datetime from the given string"""
    formats = ["%Y-%m-%d",  "%m/%d/%y", "%m/%d/%Y", "%b %Y", "%b %y", "%m/xx/%y",
               "%a %b %d %Y", "%B %d %Y %H:%M", "%b %d %Y %H:%M",
               "%B %d %Y", "%b %d %Y",'%a %b %d, %Y']
    if format is not None:
        formats.insert(0,format)
    if not isinstance(date, basestring):
        date = str(date)
    d = date
    tz = datetime.timedelta(0)
    if re.match('.+\s+ES?T$',date):
        tz = datetime.timedelta(hours=5)
    elif re.match('.+\s+EDT$',date):
        tz = datetime.timedelta(hours=4)
    elif re.match('.+\s+PS?T$',date):
        tz = datetime.timedelta(hours=8)
    elif re.match('.+\s+PDT$',date):
        tz = datetime.timedelta(hours=7)
    for regex,sub in date_hacks:
        d = regex.sub(sub,d)
    for f in formats:
        try:
            rv = datetime.datetime.strptime(d, f)
            rv += tz;
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

def from_isodatetime(date_time):
    """
    Convert an ISO formated date string to a datetime.datetime object
    """
    if not date_time:
        return None
    if date_time[:2]=='PT':
        if 'M' in date_time:
            dt = datetime.datetime.strptime(date_time, "PT%HH%MM%SS")
        else:
            dt = datetime.datetime.strptime(date_time, "PT%H:%M:%S")
        secs = (dt.hour*60+dt.minute)*60 + dt.second
        return datetime.timedelta(seconds=secs)
    if 'T' in date_time:
        try:
            return datetime.datetime.strptime(date_time, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC())
        except ValueError:
            pass
        try:
            return datetime.datetime.strptime(date_time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC())
        except ValueError:
            return datetime.datetime.strptime(date_time, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC())
    if not 'Z' in date_time:
        try:
            return datetime.datetime.strptime(date_time, "%Y-%m-%d")
        except ValueError:
            return datetime.datetime.strptime(date_time, "%d/%m/%Y")
    return datetime.datetime.strptime(date_time, "%H:%M:%SZ").replace(tzinfo=UTC()).time()

def toHtmlString(item, className=None):
    """Converts an object in to a form suitable for rendering in an HTML page.
    """
    rv=item
    if isinstance(item,dict):
        if className:
            rv='<table class="%s">'%className
        else:
            rv='<table>'
        for key,val in item.iteritems():
            rv.append('<tr><td>%s</td><td>%s</td></tr>'%(str(key),toHtmlString(val)))
        rv.append('</table>')
        rv = '\n'.join(rv)
    elif isinstance(item,(list,tuple)):
        rv = []
        for val in item:
            rv.append(toHtmlString(val))
        if item.__class__ == tuple:
            rv = ''.join(['(',','.join(rv),')'])
        else:
            rv = ''.join(['[',','.join(rv),']'])
        if className:
            rv = '<span class="%s">%s</span>'%(className,rv)
    elif isinstance(item,bool):
        if className is None:
            className=''
        rv = '<span class="bool-yes %s">&check;</span>'%className if item else '<span class="bool-no %s">&cross;</span>'%className
    else:
        if className:
            rv = '<span class="%s">%s</span>'%(className,str(rv))
        else:
            rv = str(rv)
    return rv

def toJson(value):
    if not value:
        return value
    try:
        return json.dumps(value)
    except ValueError:
        return value

def xmlSafe(value):
    """Convert the given string to a format that is safe for inclusion in an XML document.
    """
    return value.replace('&','&amp;')

def scale_timedelta(delta, num, denom):
    """Scale the given timedelta, avoiding overflows"""
    secs = num * delta.seconds
    msecs = num* delta.microseconds
    secs += msecs / 1000000.0
    return secs / denom

def toBase64(value):
    return base64.b64encode(value)
    
def toUuid(value):
    if not isinstance(value, basestring):
        value = value.encode('hex')
    value = value.upper()
    return '-'.join([value[:8], value[8:12], value[12:16], value[16:20], value[20:] ])

def sizeFormat(value, binary=True):
    units = ['G', 'M', 'K', '']
    mult = 1024 if binary else 1000
    while value > mult and units:
        units.pop()
        value = value // mult
    if not units:
        units = 'T'
    return '{:d}{}B'.format(value, units[-1])
#
# The following code is from djangoappengine/utils.py
#
try:
    from google.appengine.api import apiproxy_stub_map

    have_appserver = bool(apiproxy_stub_map.apiproxy.GetStub('datastore_v3'))
    on_production_server = have_appserver and not os.environ.get('SERVER_SOFTWARE', '').lower().startswith('devel')
except ImportError:
    pass
