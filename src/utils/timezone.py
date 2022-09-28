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

import datetime
import re

# A UTC class, see https://docs.python.org/2.7/library/datetime.html#datetime.tzinfo
class UTC(datetime.tzinfo):
    """UTC"""
    ZERO = datetime.timedelta(0)

    def __repr__(self):
        return "UTC()"

    def utcoffset(self, dt):
        return self.ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return self.ZERO


class FixedOffsetTimeZone(datetime.tzinfo):
    """Fixed offset in hours and minutes east from UTC."""

    tzinfo_re = re.compile(r'^(?P<delta>[+-])(?P<hour>\d+):(?P<minute>\d+)$')

    def __init__(self, delta_str):
        tz_match = self.tzinfo_re.match(delta_str)
        if tz_match is None:
            raise ValueError(
                r'Failed to parse timezone {}'.format(delta_str))
        offset = int(tz_match.group('hour'), 10) * 60
        offset += int(tz_match.group('minute'), 10)
        if tz_match.group('delta') == '-':
            offset = -offset
        self.__offset = datetime.timedelta(minutes=offset)
        self.__name = delta_str

    def __repr__(self):
        return 'FixedOffsetTimeZone({})'.format(self.__name)

    def utcoffset(self, dt):
        return self.__offset

    def tzname(self, dt):
        return self.__name

    def dst(self, dt):
        return datetime.timedelta(0)
