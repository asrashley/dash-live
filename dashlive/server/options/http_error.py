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

from dashlive.utils.date_time import from_isodatetime

from .dash_option import DashOption
from .types import OptionUsage

def _errors_from_string(value: str) -> list[tuple[int, str]]:
    if value.lower() in ['', 'none']:
        return []
    items: list[tuple] = []
    for val in value.split(','):
        code, pos = val.split('=')
        try:
            pos = int(pos, 10)
        except ValueError:
            pos = from_isodatetime(pos)
        items.append((int(code, 10), pos))
    return items

def http_error_factory(use: str, description: str):
    prefix = use[0]
    return DashOption(
        usage=OptionUsage.from_string(use),
        short_name=f'{prefix}he',
        full_name=f'{use}Errors',
        title=f'{description} HTTP errors',
        description=f'Cause an HTTP error to be generated when requesting {description}',
        from_string=_errors_from_string,
        cgi_name=f'{prefix}err',
        cgi_type='<code>=<num|isoDateTime>,..')


ManifestHttpError = http_error_factory('manifest', 'a manifest')

VideoHttpError = http_error_factory('video', 'video fragments')

AudioHttpError = http_error_factory('audio', 'audio fragments')

TextHttpError = http_error_factory('text', 'text fragments')

FailureCount = DashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO | OptionUsage.TEXT),
    short_name='hfc',
    full_name='failureCount',
    title='HTTP failure count',
    description=(
        'Number of times to respond with a 5xx error before ' +
        'accepting the request. Only relevant in combination ' +
        'with one of the error injection parameters (e.g. v503, m503).'),
    from_string=DashOption.int_or_none_from_string,
    cgi_name='failures',
    cgi_type='<number>')
