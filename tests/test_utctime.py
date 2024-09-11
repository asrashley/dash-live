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
import struct
import unittest
import urllib.parse

import flask

from dashlive.server.options.utc_time_options import NTP_POOLS
from dashlive.server.options.repository import OptionsRepository
from dashlive.server.requesthandler.cgi_parameter_collection import CgiParameterCollection
from dashlive.server.requesthandler.time_source_context import TimeSourceContext
from dashlive.utils.date_time import from_isodatetime
from dashlive.utils.timezone import UTC

from .mixins.flask_base import FlaskTestBase
from .mixins.mock_time import MockTime

class TestUtcTime(FlaskTestBase):
    NOW = "2023-07-18T20:10:02Z"

    @MockTime(NOW)
    def test_head_request(self):
        url = flask.url_for('time', method='head')
        response = self.client.head(url)
        self.assert200(response)
        self.assertEqual(response.headers['Date'], 'Tue, 18 Jul 2023 20:10:02 UTC')
        self.assertEqual(response.headers['Content-Type'], 'text/plain')

    @MockTime(NOW)
    def test_xsd_request(self):
        url = flask.url_for('time', method='xsd')
        response = self.client.get(url)
        self.assert200(response)
        self.assertEqual(response.headers['Date'], 'Tue, 18 Jul 2023 20:10:02 UTC')
        self.assertEqual(response.headers['Content-Type'], 'text/plain')
        self.assertEqual(response.text, self.NOW)

    @MockTime(NOW)
    def test_iso_request(self):
        url = flask.url_for('time', method='iso')
        response = self.client.get(url)
        self.assert200(response)
        self.assertEqual(response.headers['Date'], 'Tue, 18 Jul 2023 20:10:02 UTC')
        self.assertEqual(response.headers['Content-Type'], 'text/plain')
        self.assertEqual(response.text, '2023-W29-2T20:10:02Z')

    @MockTime(NOW)
    def test_ntp_request(self):
        url = flask.url_for('time', method='http-ntp')
        response = self.client.get(url)
        self.assert200(response)
        self.assertEqual(response.headers['Date'], 'Tue, 18 Jul 2023 20:10:02 UTC')
        self.assertEqual(response.headers['Content-Type'], 'application/octet-stream')
        data = response.get_data(as_text=False)
        parts = struct.unpack('>II', data)
        ntp_epoch = datetime.datetime(year=1900, month=1, day=1, tzinfo=UTC())
        seconds = (from_isodatetime(self.NOW) - ntp_epoch).total_seconds()
        self.assertEqual(parts[0], seconds)
        self.assertEqual(parts[1], 0)

    def test_scheme_id_uri_selection(self) -> None:
        test_cases: list[tuple[str, str]] = [
            ('direct', 'urn:mpeg:dash:utc:direct:2014'),
            ('head', 'urn:mpeg:dash:utc:http-head:2014'),
            ('http-ntp', 'urn:mpeg:dash:utc:http-ntp:2014'),
            ('iso', 'urn:mpeg:dash:utc:http-iso:2014'),
            ('ntp', 'urn:mpeg:dash:utc:ntp:2014'),
            ('sntp', 'urn:mpeg:dash:utc:sntp:2014'),
            ('xsd', 'urn:mpeg:dash:utc:http-xsdate:2014'),
        ]
        defaults = OptionsRepository.get_default_options()
        cgi_params = CgiParameterCollection(
            audio={}, video={}, text={}, manifest={}, patch={}, time={})
        for method, scheme_id in test_cases:
            options = OptionsRepository.convert_cgi_options(
                {'time': method}, defaults=defaults)
            tsc = TimeSourceContext(
                options, cgi_params, datetime.datetime.fromisoformat(self.NOW))
            self.assertEqual(tsc.schemeIdUri, scheme_id)

    def test_cgi_params(self) -> None:
        cgi_params = CgiParameterCollection(
            audio={}, video={}, text={}, manifest={}, patch={},
            time={'drift': 2})
        options = OptionsRepository.convert_cgi_options({'time': 'iso'})
        tsc = TimeSourceContext(
            options, cgi_params, datetime.datetime.fromisoformat(self.NOW))
        url = flask.url_for('time', method='iso', drift='2')
        url = urllib.parse.urljoin(flask.request.host_url, url)
        self.assertEqual(tsc.value, url)

    def test_default_ntp_servers(self) -> None:
        defaults = OptionsRepository.get_default_options()
        cgi_params = CgiParameterCollection(
            audio={}, video={}, text={}, manifest={}, patch={}, time={})
        for alg in ['ntp', 'sntp']:
            options = OptionsRepository.convert_cgi_options(
                {'time': alg}, defaults=defaults)
            self.assertEqual(options.ntpSources, [])
            tsc = TimeSourceContext(
                options, cgi_params,
                datetime.datetime.fromisoformat(self.NOW))
            default_pool = NTP_POOLS[TimeSourceContext.DEFAULT_NTP_POOL]
            self.assertEqual(tsc.value, ' '.join(default_pool))

    def test_set_ntp_pool(self) -> None:
        defaults = OptionsRepository.get_default_options()
        cgi_params = CgiParameterCollection(
            audio={}, video={}, text={}, manifest={}, patch={}, time={})
        for pool in NTP_POOLS.keys():
            for alg in ['ntp', 'sntp']:
                options = OptionsRepository.convert_cgi_options({
                    'time': alg,
                    'ntp_servers': pool,
                }, defaults=defaults)
                self.assertEqual(options.ntpSources, [pool])
                tsc = TimeSourceContext(
                    options, cgi_params,
                    datetime.datetime.fromisoformat(self.NOW))
                self.assertEqual(tsc.value, ' '.join(NTP_POOLS[pool]))

    def test_set_ntp_servers(self) -> None:
        defaults = OptionsRepository.get_default_options()
        cgi_params = CgiParameterCollection(
            audio={}, video={}, text={}, manifest={}, patch={}, time={})
        options = OptionsRepository.convert_cgi_options({
            'time': 'ntp',
            'ntp_servers': '1.time.unit.test,2.time.unit.test',
        }, defaults=defaults)
        self.assertEqual(options.ntpSources,
                         ['1.time.unit.test', '2.time.unit.test'])
        tsc = TimeSourceContext(
            options, cgi_params, datetime.datetime.fromisoformat(self.NOW))
        self.assertEqual(tsc.value, '1.time.unit.test 2.time.unit.test')


if __name__ == '__main__':
    unittest.main()
