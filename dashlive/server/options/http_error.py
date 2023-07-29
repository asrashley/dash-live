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

from .dash_option import DashOption

def http_error_factory(prefix: str, use: str):
    cgi_names = []
    for name in ['404', '410', '503', '504']:
        cgi_names.append(f'{prefix}{name}')
    return DashOption(
        name=f'{prefix}he',
        title=f'{use} HTTP errors',
        description=f'Cause an HTTP error to be generated when requesting {use}',
        cgi_name=cgi_names,
        cgi_type='<num>,<num>,..')


ManifestHttpError = http_error_factory('m', 'a manifest')

VideoHttpError = http_error_factory('v', 'video fragments')

AudioHttpError = http_error_factory('a', 'audio fragments')

FailureCount = DashOption(
    name='hfc',
    title='HTTP failure count',
    description=(
        'Number of times to respond with a 5xx error before ' +
        'accepting the request. Only relevant in combination ' +
        'with one of the error injection parameters (e.g. v503, m503).'),
    cgi_name='failures',
    cgi_type='<number>')
