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

from dashlive.server.requesthandler.base import RequestHandlerBase
from dashlive.server.requesthandler.exceptions import CsrfFailureException

from .mixins.flask_base import FlaskTestBase

class MockHandler(RequestHandlerBase):
    def is_https_request(self) -> bool:
        return True

class TestRequestHandlerBase(FlaskTestBase):
    @patch.object(flask, 'request')
    def test_https_request_uri(self, mock_request):
        mock_request.endpoint = 'home'
        mock_request.headers = {
            'Origin': 'a.unit.test',
        }
        mock_request.scheme = 'https'
        mock_request.url = 'https://a.unit/test/'
        rhb = RequestHandlerBase()
        context = rhb.create_context()
        self.assertStartsWith(context['request_uri'], 'https://')

        mock_request.scheme = 'http'
        mock_request.url = 'http://a.unit/test/'
        context = rhb.create_context()
        self.assertStartsWith(context['request_uri'], 'http://')
        with patch.dict('dashlive.server.app.environ', {'HTTPS': 'on'}, clear=True):
            context = rhb.create_context()
            self.assertStartsWith(context['request_uri'], 'https://')

    @patch.object(flask, 'request')
    def test_x_http_scheme_header(self, mock_request):
        mock_request.endpoint = 'home'
        mock_request.headers = {
            'Origin': 'a.unit.test',
            'X-HTTP-Scheme': 'https',
        }
        mock_request.scheme = 'http'
        mock_request.url = 'http://a.unit/test/'
        rhb = RequestHandlerBase()
        context = rhb.create_context()
        self.assertStartsWith(context['request_uri'], 'https://')

    @patch.object(flask, 'request')
    def test_missing_csrf_cookie(self, req) -> None:
        req.cookies = {}
        rhb = RequestHandlerBase()
        with self.assertRaises(CsrfFailureException) as cm:
            rhb.check_csrf('files', {})
        self.assertIn('cookie not present', str(cm.exception))

    @patch.object(flask, 'request')
    def test_invalid_csrf_cookie(self, req) -> None:
        req.cookies = {
            RequestHandlerBase.CSRF_COOKIE_NAME: None,
        }
        rhb = RequestHandlerBase()
        with self.assertRaises(CsrfFailureException) as cm:
            rhb.check_csrf('files', {})
        self.assertIn('cookie not valid', str(cm.exception))

    @patch.object(flask, 'request')
    def test_csrf_signature_mismatch(self, req) -> None:
        req.cookies = {
            RequestHandlerBase.CSRF_COOKIE_NAME: 'Bj2sVUJfupva1WK-KamSk7BrI4_MFyWYpqYJjt7d-ts',
        }
        req.headers = {
            'Origin': 'a.unit.test',
        }
        req.scheme = 'http'
        req.url = 'http://a.unit/test/'
        rhb = RequestHandlerBase()
        params = {
            'csrf_token': 'vvkRhkxfb%27KdO5RtEtzY6ULLfGpOuBks2AN/Q%3D%27',
        }
        with self.assertRaises(CsrfFailureException) as cm:
            rhb.check_csrf('streams', params)
        self.assertIn('signatures do not match', str(cm.exception))


if __name__ == '__main__':
    unittest.main()
