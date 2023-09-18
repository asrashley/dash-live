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
import binascii
from dataclasses import dataclass
import datetime
import json
from typing import Any, ClassVar

from flask import Blueprint, current_app, url_for

from dashlive.utils.objects import flatten_iterable
from dashlive.utils.date_time import (
    parse_date,
    toIsoDuration,
    to_iso_datetime,
    from_isodatetime
)

@dataclass(slots=True, frozen=True)
class ScriptTag:
    SCRIPT_TEMPLATE: ClassVar[str] = r'<script src="{js_filename}" type="text/javascript"></script>'

    filename: str
    dev: bool

    def __html__(self) -> str:
        mode = 'dev' if self.dev else 'prod'
        minify = '' if self.dev else '.min'
        js_filename = url_for(
            'static', filename=f'js/{mode}/{self.filename}{minify}.js')
        return self.SCRIPT_TEMPLATE.format(js_filename=js_filename)


@dataclass(slots=True, frozen=True)
class HtmlSafeString:
    html: str

    def __html__(self) -> str:
        return self.html


custom_tags = Blueprint('custom_tags', __name__)

@custom_tags.app_template_filter()
def dateTimeFormat(value: str | datetime.datetime | None, fmt: str) -> str:
    """ Format a date using the given format"""
    if value is None:
        return value
    if isinstance(value, str):
        if 'T' in value:
            value = from_isodatetime(value)
        else:
            value = parse_date(value)
        if value is None:
            return value
    return value.strftime(fmt)

@custom_tags.app_template_filter()
def timeDelta(value: datetime.timedelta | None) -> str:
    if value is None:
        return ''
    ticks = value / datetime.timedelta(milliseconds=10)
    seconds = int(ticks // 100)
    mins = int(seconds // 60)
    hours = int(mins // 60)
    mins %= 60
    seconds %= 60
    ticks = int(ticks) % 100
    if hours:
        return f'{hours:d}:{mins:#02d}:{seconds:#02d}.{ticks:#02d}'
    if mins:
        return f'{mins:d}:{seconds:#02d}.{ticks:#02d}'
    return f'{seconds:#02d}.{ticks:#02d}'

@custom_tags.app_template_filter()
def default(value: Any, default_value: Any) -> Any:
    if value is None:
        return default_value
    if value or isinstance(value, bool):
        return value
    return default_value

@custom_tags.app_template_filter()
def sizeFormat(value: int, binary: bool = True, units: str = 'B') -> str:
    prefix = ['G', 'M', 'K', '']
    mult = 1024 if binary else 1000
    while value > mult and prefix:
        prefix.pop()
        value = value // mult
    if not prefix:
        prefix = 'T'
    return f'{value} {prefix[-1]}{units}'

@custom_tags.app_template_filter(name='base64')
def toBase64(value):
    return str(base64.b64encode(value), 'ascii')

@custom_tags.app_template_filter()
def toHtmlString(item, className=None):
    """
    Converts an object in to a form suitable for rendering in an HTML page.
    """
    rv = item
    if isinstance(item, dict):
        if className:
            rv = [f'<table class="{className}">']
        else:
            rv = ['<table>']
        for key, val in item.items():
            rv.append('<tr><td>{}</td><td>{}</td></tr>'.format(
                str(key), toHtmlString(val).html))
        rv.append('</table>')
        rv = '\n'.join(rv)
    elif isinstance(item, (list, tuple)):
        rv = []
        for val in item:
            rv.append(toHtmlString(val).html)
        if item.__class__ == tuple:
            rv = ''.join(['(', ','.join(rv), ')'])
        else:
            rv = ''.join(['[', ','.join(rv), ']'])
        if className:
            rv = f'<span class="{className}">{rv}</span>'
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
        rv = '<span class="{}">{}</span>'.format(' '.join(classes), entity)
    else:
        if className:
            rv = f'<span class="{className}">{rv:s}</span>'
        else:
            rv = str(rv)
    return HtmlSafeString(rv)

@custom_tags.app_template_filter()
def toJson(value, indent: int | None = None):
    if value is None:
        return value
    try:
        if isinstance(value, (dict, list, set, tuple)):
            value = flatten_iterable(value)
        return json.dumps(value, indent=indent)
    except ValueError as err:
        return str(err)

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
        rv.append(f'{k}="{value[k]}"')
    return ' '.join(rv)

@custom_tags.app_template_filter()
def isoDateTime(value):
    return to_iso_datetime(value)

@custom_tags.app_template_filter()
def isoDuration(value):
    return toIsoDuration(value)

@custom_tags.app_template_filter()
def frameRateFraction(value):
    if (value - int(value)) < 0.01:
        return int(value)
    num = int(round(value * 1001))
    return f'{num}/1001'

@custom_tags.app_template_filter()
def length(value: str | None) -> int:
    if value is None:
        return 0
    return len(value)

@custom_tags.app_template_global()
def import_script(filename: str) -> ScriptTag:
    debug = current_app.config.get('JS_DEBUG', False)
    return ScriptTag(filename, debug)

@custom_tags.app_template_global()
def sort_icon(name: str, order: str, reverse: bool) -> str:
    if name != order:
        return ''
    if reverse:
        entity = '&and;'
    else:
        entity = '&or;'
    return HtmlSafeString(f'<span class="float-right sort-arrow">{entity}</span>')
