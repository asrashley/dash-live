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

from typing import Dict, List, Optional, Tuple
import urllib.parse

from dashlive.utils.json_object import JsonObject
from dashlive.management.http import HttpSession, HttpResponse

class HttpResponseWrapper(HttpResponse):
    def __init__(self, response):
        self.status_code = response.status_code
        self.response = response

    @property
    def text(self) -> str:
        return self.response.get_data(as_text=True)

    @property
    def headers(self) -> Dict:
        return self.response.headers

    @property
    def content(self) -> bytes:
        return self.response.get_data(as_text=False)

    def json(self) -> JsonObject:
        return self.response.json


class ClientHttpSession(HttpSession):
    def __init__(self, client) -> None:
        self.client = client

    def get(self, url: str, params: Optional[Dict] = None,
            **kwargs) -> HttpResponse:
        """Make a GET request"""
        if params is None:
            return HttpResponseWrapper(self.client.get(url, **kwargs))
        if '?' not in url:
            url += '?'
        url += self.params_to_str(params)
        return HttpResponseWrapper(self.client.get(url, **kwargs))

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
