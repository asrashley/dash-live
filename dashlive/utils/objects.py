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

from collections.abc import Iterable
import datetime
import decimal
from typing import AbstractSet

from dashlive.utils.date_time import to_iso_datetime, toIsoDuration

def flatten(value, convert_numbers=False, pure=True, exclude: AbstractSet | None = None):
    """
    Converts a value in to a form suitable for storage.
    It will inspect the type of the value to try to detect
    if it needs to be converted to a canonical
    form before it can be processed for storage.
    A list, tuple or dictionary will be recursively flattened.
    """
    if value is None:
        return None
    if isinstance(value, str):
        if pure:
            return str(value).replace("'", "\'")
        return value
    if hasattr(value, 'toJSON'):
        return value.toJSON(pure=pure, exclude=exclude)
    if isinstance(value, Iterable):
        return flatten_iterable(value, convert_numbers, exclude=exclude)
    if isinstance(value, (datetime.date, datetime.datetime, datetime.time)):
        return to_iso_datetime(value)
    if isinstance(value, (datetime.timedelta)):
        return toIsoDuration(value)
    if convert_numbers and isinstance(value, int):
        return f'{value:d}'
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (list, set, tuple)):
        return flatten_iterable(list(value), exclude=exclude)
    if isinstance(value, dict):
        return flatten_iterable(value, exclude=exclude)
    return value

def flatten_iterable(items, convert_numbers=False, exclude: AbstractSet | None = None):
    """
    Converts an object in to a form suitable for storage.
    flatten_iterable will take a dictionary, list or tuple and inspect each item
    in the object looking for items such as datetime.datetime objects
    that need to be converted to a canonical form before
    they can be processed for storage.
    """
    if exclude is None:
        exclude = set()
    if isinstance(items, dict):
        rv = {}
        for key, value in items.items():
            if callable(value) or key in exclude:
                continue
            rv[key] = flatten(value)
        return rv
    rv = []
    for item in items:
        if callable(item):
            continue
        item = flatten(item)
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
        items = [as_python(v) for v in list(value)]
        value = '[{}]'.format(', '.join(items))
    elif isinstance(value, (dict)):
        items = []
        clz = value.get('_type', None)
        for k, v in value.items():
            if k == '_type':
                continue
            if clz is None:
                items.append(f'"{k}": {as_python(v)}')
            else:
                items.append(f'{k}={as_python(v)}')
        if clz is None:
            value = '{' + ', '.join(items) + '}'
        else:
            value = '{}({})'.format(clz, ', '.join(items))
    elif wrap_strings and isinstance(value, (str)):
        if '"' in value:
            value = ''.join(["'", value, "'"])
        else:
            value = ''.join(['"', value, '"'])
    elif isinstance(value, (datetime.date, datetime.datetime, datetime.time)):
        value = 'utils.from_isodatetime("%s")' % (to_iso_datetime(value))
    elif isinstance(value, (datetime.timedelta)):
        value = 'utils.from_isodatetime("%s")' % (toIsoDuration(value))
    elif isinstance(value, decimal.Decimal):
        value = 'decimal.Decimal(%s)' % (value)
    else:
        value = str(value)
    return value

def pick_items(src: dict, keys: AbstractSet[str]) -> dict:
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

def dict_to_cgi_params(params: dict[str, str]) -> str:
    """
    Convert dictionary into a CGI parameter string
    """
    if not params:
        return ''
    keys = list(params.keys())
    keys.sort()
    lst = []
    for name in keys:
        val = params[name]
        lst.append(f'{name}={val}')
    return '?' + '&'.join(lst)

def merge(*items):
    """
    Produce a dictionary that merges all of the dictionaries
    passed to merge()
    """
    rv = {}
    for item in items:
        rv.update(item)
    return rv
