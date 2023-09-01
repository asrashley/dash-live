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
import urllib

import requests

from dashlive.server.routes import routes

from .http import HttpSession
from .info import StreamInfo, UserInfo

class LoginFailureException(Exception):
    """
    Exception that is thrown when login fails
    """
    pass

class ManagementBase:
    """
    Base class for downloading and uploading server management
    """
    def __init__(self, url: str, username: str, password: str,
                 session: HttpSession | None = None) -> None:
        self.base_url = url
        self.username = username
        self.password = password
        if session:
            self.session = session
        else:
            self.session = requests.Session()
        self.csrf_tokens = {}
        self.keys = {}
        self.streams: dict[str, StreamInfo] = {}
        self.log = logging.getLogger('management')
        self.user: UserInfo | None = None

    def url_for(self, name, **kwargs) -> str:
        route = routes[name]
        path = route.formatTemplate.format(**kwargs)
        return urllib.parse.urljoin(self.base_url, path)

    def login(self) -> bool:
        if self.user:
            return True
        login_url = self.url_for('login')
        self.log.debug('GET %s', login_url)
        result = self.session.get(f'{login_url}?ajax=1')
        if result.status_code != 200:
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            raise LoginFailureException(f'GET HTTP error: {result.status_code}')
        fields = {
            "username": self.username,
            "password": self.password,
            "rememberme": 0,
            "action": "Login",
            "csrf_token": result.json()['csrf_token']
        }
        result = self.session.post(login_url, json=fields)
        if result.status_code != 200:
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            raise LoginFailureException(f'POST HTTP error: {result.status_code}')
        js = result.json()
        if js.get('error'):
            raise LoginFailureException(js['error'])
        self.user = UserInfo(**js['user'])
        return True

    def get_media_info(self, with_details: bool = False) -> bool:
        if not self.login():
            return False
        url = self.url_for('list-streams')
        self.log.debug('GET %s', url)
        result = self.session.get(url, params={'ajax': 1})
        if result.status_code != 200:
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            return False
        js = result.json()
        self.csrf_tokens.update(js['csrf_tokens'])
        self.keys = {}
        self.streams = {}
        for k in js['keys']:
            kid = k['kid']
            self.log.debug('KID %s: computed=%s', kid, k['computed'])
            self.keys[kid] = k
        for s in js['streams']:
            self.streams[s['directory']] = StreamInfo(**s)
            self.log.debug('Stream %s: %s', s['directory'], s['title'])
            if with_details:
                st = self.get_stream_info(s['directory'])
                if st is not None:
                    self.streams[s['directory']] = st
        return True

    def get_stream_info(self, directory: str) -> StreamInfo | None:
        if directory not in self.streams:
            self.get_media_info()
        if directory not in self.streams:
            self.log.error('Failed to find information for stream "%s"', directory)
            return None
        url = self.url_for('view-stream', spk=self.streams[directory].pk)
        self.log.debug('GET %s', url)
        result = self.session.get(url, params={'ajax': 1})
        if result.status_code != 200:
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            return None
        js = result.json()
        return StreamInfo(**js)
