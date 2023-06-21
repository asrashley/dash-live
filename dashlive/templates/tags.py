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
import base64
import binascii
import json

from flask import Blueprint

from dashlive.utils.objects import flatten_iterable
from dashlive.utils.date_time import parse_date, toIsoDuration, toIsoDateTime

custom_tags = Blueprint('custom_tags', __name__)

@custom_tags.app_template_filter()
def dateTimeFormat(value, fmt):
    """ Format a date using the given format"""
    if not value:
        return value
    if isinstance(value, basestring):
        value = parse_date(value)
    if value is None:
        return value
    return value.strftime(fmt)

@custom_tags.app_template_filter()
def default(value, default_value):
    if value is None:
        return default_value
    if value or isinstance(value, bool):
        return value
    return default_value

@custom_tags.app_template_filter()
def sizeFormat(value, binary=True):
    units = ['G', 'M', 'K', '']
    mult = 1024 if binary else 1000
    while value > mult and units:
        units.pop()
        value = value // mult
    if not units:
        units = 'T'
    return '{:d}{}B'.format(value, units[-1])

@custom_tags.app_template_filter(name='base64')
def toBase64(value):
    return str(base64.b64encode(value), 'ascii')

class HtmlSafeString:
    def __init__(self, html: str) -> None:
        self.html = html

    def __html__(self) -> str:
        return self.html

@custom_tags.app_template_filter()
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
        for key, val in item.items():
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
    return HtmlSafeString(rv)

@custom_tags.app_template_filter()
def toJson(value, indent=0):
    if value is None:
        return value
    try:
        if isinstance(value, (dict, list, set, tuple)):
            value = flatten_iterable(value)
        return json.dumps(value, indent=indent)
    except ValueError:
        return value

@custom_tags.app_template_filter(name='uuid')
def toUuid(value):
    if isinstance(value, bytes):
        value = str(binascii.b2a_hex(value), 'ascii')
    value = value.upper()
    return '-'.join([
        value[:8], value[8:12], value[12:16], value[16:20],
        value[20:]])

@custom_tags.app_template_filter()
def trueFalse(value):
    """
    Returns a "true" or "false" string for the provided boolean
    """
    if value:
        return "true"
    return "false"

@custom_tags.app_template_filter()
def xmlSafe(value):
    """
    Convert the given string to a format that is safe for inclusion
    in an XML document.
    """
    return value.replace('&', '&amp;')

@custom_tags.app_template_filter()
def sortedAttributes(value):
    """
    Output the provided dictionary as a key="value" string with the
    keys sorted alphabetically
    """
    if not isinstance(value, dict):
        return ''
    keys = list(value.keys())
    if not keys:
        return ''
    keys.sort()
    rv = ['']
    for k in keys:
        rv.append('{0}="{1}"'.format(k, value[k]))
    return ' '.join(rv)

@custom_tags.app_template_filter()
def isoDateTime(value):
    return toIsoDateTime(value)

@custom_tags.app_template_filter()
def isoDuration(value):
    return toIsoDuration(value)
