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

import logging
from typing import Dict, List, Optional, Tuple
import unittest
import urllib.parse

import flask

from dashlive.utils.json_object import JsonObject
from dashlive.upload import HttpSession, PopulateDatabase, HttpResponse

from .flask_base import FlaskTestBase

class HttpResponseWrapper(HttpResponse):
    def __init__(self, response):
        self.status_code = response.status_code
        self.headers = response.headers
        self.text = response.text
        self.response = response

    def json(self) -> JsonObject:
        return self.response.json


class ClientHttpSession(HttpSession):
    def __init__(self, client) -> None:
        self.client = client

    def get(self, url: str, params: Optional[Dict] = None) -> HttpResponse:
        """Make a GET request"""
        if params is None:
            return HttpResponseWrapper(self.client.get(url))
        if '?' not in url:
            url += '?'
        url += self.params_to_str(params)
        return HttpResponseWrapper(self.client.get(url))

    def put(self, url: str,
            params: Optional[JsonObject] = None,
            **kwargs):
        """Make a PUT request"""
        if params is not None:
            if '?' not in url:
                url += '?'
            url += self.params_to_str(params)
        return HttpResponseWrapper(self.client.put(url, **kwargs))

    def post(self, url: str,
             data: Optional[bytes] = None,
             files: Optional[List[Tuple]] = None,
             params: Optional[JsonObject] = None,
             json: Optional[JsonObject] = None,
             content_type: Optional[str] = None) -> HttpResponse:
        """Make a POST request"""
        kwargs = {}
        if content_type is not None:
            kwargs['content_type'] = content_type
        if data is not None:
            kwargs['data'] = data
        if files is not None:
            if data is None:
                kwargs['data'] = {}
            for name, parts in files:
                filename, fp, mimeType = parts
                kwargs['data'][name] = (fp, filename, mimeType)
        if json is not None:
            kwargs['json'] = json
        if params is not None:
            if '?' not in url:
                url += '?'
            url += self.params_to_str(params)
        response = self.client.post(url, **kwargs)
        # see https://github.com/pallets/werkzeug/issues/1785
        # as the test files are larger than 500KB, a temp file is
        # created that the test client doesn't close
        if files is not None:
            response.request.input_stream.close()
        return HttpResponseWrapper(response)

    @staticmethod
    def params_to_str(params: Dict) -> str:
        args: List[str] = []
        for key, value in params.items():
            if isinstance(value, str):
                value = urllib.parse.quote_plus(value, encoding='utf-8')
            args.append(f'{key}={value}')
        return '&'.join(args)


class TestPopulateDatabase(FlaskTestBase):
    def test_populate_database(self) -> None:
        self.login_user(username=self.MEDIA_USER, password=self.MEDIA_PASSWORD)
        tmpdir = self.create_upload_folder()
        with self.app.app_context():
            self.app.config['BLOB_FOLDER'] = tmpdir
        pd = PopulateDatabase(
            url=flask.url_for('home'),
            username=self.MEDIA_USER,
            password=self.MEDIA_PASSWORD,
            session=ClientHttpSession(self.client))
        jsonfile = self.FIXTURES_PATH / 'upload.json'
        result = pd.populate_database(str(jsonfile))
        self.assertTrue(result)


if __name__ == "__main__":
    mm_log = logging.getLogger('PopulateDatabase')
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s: %(funcName)s:%(lineno)d: %(message)s'))
    mm_log.addHandler(ch)
    # logging.getLogger().setLevel(logging.DEBUG)
    # mm_log.setLevel(logging.DEBUG)
    unittest.main()
