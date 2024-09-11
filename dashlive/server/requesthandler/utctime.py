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
import logging
import struct

import flask

from dashlive.utils.date_time import to_iso_datetime
from dashlive.utils.timezone import UTC

from .base import RequestHandlerBase

class UTCTimeHandler(RequestHandlerBase):
    def head(self, method: str) -> flask.Response:
        return self.get(method)

    def get(self, method: str) -> flask.Response:
        try:
            options = self.calculate_options('live', flask.request.args)
        except ValueError as err:
            logging.error('Invalid CGI parameters: %s', err)
            return flask.make_response('Invalid CGI parameters', 400)
        now = datetime.datetime.now(tz=UTC())
        if options.clockDrift:
            now -= datetime.timedelta(seconds=options.clockDrift)
        headers = {
            'Content-Type': 'text/plain',
            'Date': now.strftime(r'%a, %d %b %Y %H:%M:%S %Z'),
        }
        rv = ''
        if method == 'xsd':
            rv = to_iso_datetime(now)
        elif method == 'iso':
            # This code picks an obscure option from ISO 8601, so that a simple parser
            # will fail
            isocal = now.isocalendar()
            rv = '%04d-W%02d-%dT%02d:%02d:%02dZ' % (
                isocal[0], isocal[1], isocal[2], now.hour, now.minute, now.second)
        elif method == 'http-ntp':
            # NTP epoch is 1st Jan 1900
            epoch = datetime.datetime(
                year=1900, month=1, day=1, tzinfo=UTC())
            seconds = (now - epoch).total_seconds()
            fraction = seconds - int(seconds)
            seconds = int(seconds) % (1 << 32)
            fraction = int(fraction * (1 << 32))
            # See RFC5905 for "NTP Timestamp format"
            rv = struct.pack('>II', seconds, fraction)
            headers['Content-Type'] = 'application/octet-stream'
        return flask.make_response((rv, 200, headers))
