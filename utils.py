import datetime, math, os, re


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
    """ Convert a dateTime to number of seconds since the Unix epoch
    """
    epoch = datetime.datetime(year=1970, month=1, day=1, tzinfo=UTC())
    return (dt - epoch).total_seconds()

def toIsoDateTime(value):
    """ Convert a datetime to an ISO8601 formatted dateTime string.
    @param {datetime} value the dateTime to convert
    @returns {string} an ISO8601 formatted version of the dateTime
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
     @param {number} secs the duration to convert, in seconds
     @returns {string} an ISO8601 formatted version of the duration
     """
    if isinstance(secs,str):
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
        rv.append('%fS'%secs)
    return ''.join(rv)

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

def scale_timedelta(delta, num, denom):
    """Scale the given timedelta, avoiding overflows"""
    secs = num * delta.seconds
    msecs = num* delta.microseconds
    secs += msecs / 1000000.0
    return secs / denom

#
# The following code is from djangoappengine/utils.py
#
try:
    from google.appengine.api import apiproxy_stub_map

    have_appserver = bool(apiproxy_stub_map.apiproxy.GetStub('datastore_v3'))
    on_production_server = have_appserver and not os.environ.get('SERVER_SOFTWARE', '').lower().startswith('devel')
except ImportError:
    pass
