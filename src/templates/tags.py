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
import json

from utils.objects import flatten_iterable
from utils.date_time import parse_date

def dateTimeFormat(value, fmt):
    """ Format a date using the given format"""
    if not value:
        return value
    if isinstance(value, basestring):
        value = parse_date(value)
    if value is None:
        return value
    return value.strftime(fmt)

def default(value, default_value):
    if value is None:
        return default_value
    if value or isinstance(value, bool):
        return value
    return default_value

def sizeFormat(value, binary=True):
    units = ['G', 'M', 'K', '']
    mult = 1024 if binary else 1000
    while value > mult and units:
        units.pop()
        value = value // mult
    if not units:
        units = 'T'
    return '{:d}{}B'.format(value, units[-1])

def toBase64(value):
    return base64.b64encode(value)

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
            classes = []
        else:
            classes = [className]
        if item:
            classes.append("bool-yes")
            entity = r"&check;"
        else:
            classes.append("bool-no")
            entity = r"&cross;"
        rv = '<span class="{0}">{1}</span>'.format(' '.join(classes), entity)
    else:
        if className:
            rv = '<span class="{0}">{1:s}</span>'.format(className, rv)
        else:
            rv = str(rv)
    return rv

def toJson(value, indent=0):
    if value is None:
        return value
    try:
        if isinstance(value, (dict, list, set, tuple)):
            value = flatten_iterable(value)
        return json.dumps(value, indent=indent)
    except ValueError:
        return value

def toUuid(value):
    if not isinstance(value, basestring):
        value = value.encode('hex')
    value = value.upper()
    return '-'.join([
        value[:8], value[8:12], value[12:16], value[16:20],
        value[20:]])

def xmlSafe(value):
    """
    Convert the given string to a format that is safe for inclusion
    in an XML document.
    """
    return value.replace('&', '&amp;')
