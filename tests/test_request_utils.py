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

import unittest
from unittest.mock import patch

import flask

from dashlive.server.requesthandler.utils import add_allowed_origins

from .mixins.flask_base import FlaskTestBase

class TestRequestHandlerUtils(FlaskTestBase):
    @patch.object(flask, 'request')
    def test_matching_allowed_origin(self, mock_request) -> None:
        headers = {}
        with self.app.app_context():
            mock_request.headers = {
                'Origin': 'www.unit.test',
            }
            self.app.config['DASH']['ALLOWED_DOMAINS'] = 'unit.test'
            add_allowed_origins(headers)
            allowed_methods: set[str] = {
                m.strip() for m in headers["Access-Control-Allow-Methods"].split(",")
            }
            self.assertEqual(allowed_methods, {"HEAD", "GET", "POST"})
            self.assertEqual(headers["Access-Control-Allow-Origin"], 'www.unit.test')

    @patch.object(flask, 'request')
    def test_matching_allowed_origin_with_methods(self, mock_request) -> None:
        headers = {}
        with self.app.app_context():
            mock_request.headers = {
                'Origin': 'www.unit.test',
            }
            self.app.config['DASH']['ALLOWED_DOMAINS'] = 'unit.test'
            add_allowed_origins(headers, methods={"PUT", "POST"})
            allowed_methods: set[str] = {
                m.strip() for m in headers["Access-Control-Allow-Methods"].split(",")
            }
            self.assertEqual(allowed_methods, {"PUT", "POST"})
            self.assertEqual(headers["Access-Control-Allow-Origin"], 'www.unit.test')

    @patch.object(flask, 'request')
    def test_non_matching_allowed_origin(self, mock_request) -> None:
        headers = {}
        with self.app.app_context():
            mock_request.headers = {
                'Origin': 'www.unit.test',
            }
            self.app.config['DASH']['ALLOWED_DOMAINS'] = 'another.domain'
            add_allowed_origins(headers)
            self.assertNotIn("Access-Control-Allow-Methods", headers)
            self.assertNotIn("Access-Control-Allow-Origin", headers)

    @patch.object(flask, 'request')
    def test_wildcard_allowed_origin(self, mock_request) -> None:
        headers = {}
        with self.app.app_context():
            self.app.config['DASH']['ALLOWED_DOMAINS'] = '*'
            add_allowed_origins(headers)
            allowed_methods: set[str] = {
                m.strip() for m in headers["Access-Control-Allow-Methods"].split(",")
            }
            self.assertEqual(allowed_methods, {"HEAD", "GET", "POST"})
            self.assertEqual(headers["Access-Control-Allow-Origin"], '*')


if __name__ == '__main__':
    unittest.main()
