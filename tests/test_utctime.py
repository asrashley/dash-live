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
import os
import struct
import unittest

import flask

from dashlive.utils.date_time import to_iso_datetime, from_isodatetime
from dashlive.utils.timezone import UTC

from .mixins.flask_base import FlaskTestBase

class TestUtcTime(FlaskTestBase):
    NOW = from_isodatetime("2023-07-18T20:10:02Z")

    @FlaskTestBase.mock_datetime_now(NOW)
    def test_head_request(self):
        url = flask.url_for('time', format='head')
        response = self.client.head(url)
        self.assert200(response)
        self.assertEqual(response.headers['Date'], 'Tue, 18 Jul 2023 20:10:02 UTC')
        self.assertEqual(response.headers['Content-Type'], 'text/plain')

    @FlaskTestBase.mock_datetime_now(NOW)
    def test_xsd_request(self):
        url = flask.url_for('time', format='xsd')
        response = self.client.get(url)
        self.assert200(response)
        self.assertEqual(response.headers['Date'], 'Tue, 18 Jul 2023 20:10:02 UTC')
        self.assertEqual(response.headers['Content-Type'], 'text/plain')
        self.assertEqual(response.text, to_iso_datetime(self.NOW))

    @FlaskTestBase.mock_datetime_now(NOW)
    def test_iso_request(self):
        url = flask.url_for('time', format='iso')
        response = self.client.get(url)
        self.assert200(response)
        self.assertEqual(response.headers['Date'], 'Tue, 18 Jul 2023 20:10:02 UTC')
        self.assertEqual(response.headers['Content-Type'], 'text/plain')
        self.assertEqual(response.text, '2023-W29-2T20:10:02Z')

    @FlaskTestBase.mock_datetime_now(NOW)
    def test_ntp_request(self):
        url = flask.url_for('time', format='http-ntp')
        response = self.client.get(url)
        self.assert200(response)
        self.assertEqual(response.headers['Date'], 'Tue, 18 Jul 2023 20:10:02 UTC')
        self.assertEqual(response.headers['Content-Type'], 'application/octet-stream')
        data = response.get_data(as_text=False)
        parts = struct.unpack('>II', data)
        ntp_epoch = datetime.datetime(year=1900, month=1, day=1, tzinfo=UTC())
        seconds = (self.NOW - ntp_epoch).total_seconds()
        self.assertEqual(parts[0], seconds)
        self.assertEqual(parts[1], 0)


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        logging.basicConfig()
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            TestUtcTime)

if __name__ == '__main__':
    unittest.main()
