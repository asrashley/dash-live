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

from dashlive.server.requesthandler.csrf import CsrfProtection
from dashlive.server.requesthandler.exceptions import CsrfFailureException

from .mixins.flask_base import FlaskTestBase

class TestCsrfProtection(FlaskTestBase):
    @patch.object(flask, 'request')
    def test_missing_csrf_cookie(self, req) -> None:
        req.cookies = {}
        with self.assertRaises(CsrfFailureException) as cm:
            CsrfProtection.check('files', '')
        self.assertIn('cookie not present', str(cm.exception))

    @patch.object(flask, 'request')
    def test_invalid_csrf_cookie(self, req) -> None:
        name: str = CsrfProtection.cookie_name()
        req.cookies = {
            name: None,
        }
        with self.assertRaises(CsrfFailureException) as cm:
            CsrfProtection.check('files', '')
        self.assertIn('cookie not valid', str(cm.exception))

    @patch.object(flask, 'request')
    def test_csrf_signature_mismatch(self, req) -> None:
        name: str = CsrfProtection.cookie_name()
        req.cookies = {
            name: 'Bj2sVUJfupva1WK-KamSk7BrI4_MFyWYpqYJjt7d-ts',
        }
        req.headers = {
            'Origin': 'a.unit.test',
        }
        req.scheme = 'http'
        req.url = 'http://a.unit/test/'
        csrf_token = 'vvkRhkxfb%27KdO5RtEtzY6ULLfGpOuBks2AN/Q%3D%27'
        with self.assertRaises(CsrfFailureException) as cm:
            CsrfProtection.check('streams', csrf_token)
        self.assertIn('signatures do not match', str(cm.exception))


if __name__ == '__main__':
    unittest.main()
