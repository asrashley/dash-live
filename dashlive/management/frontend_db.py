#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import logging
from pathlib import Path
import time
from typing import Any, cast
import urllib

import requests

from dashlive.management.http import HttpResponse
from dashlive.server.models.user import UserSummaryJson
from dashlive.server.requesthandler.user_management import LoginRequestJson, LoginResponseJson
from dashlive.server.routes import routes
from dashlive.utils.json_object import JsonObject

from .db_access import DatabaseAccess
from .http import HttpSession
from .info import KeyInfo, StreamInfo, UserInfo

class FrontendDatabaseAccess(DatabaseAccess):
    """
    Access to database using front-end ajax API
    """
    base_url: str
    csrf_tokens: dict[str, Any]
    keys: dict[str, KeyInfo]
    log: logging.Logger
    password: str
    session: HttpSession
    streams: dict[str, StreamInfo]
    token: str
    user: UserInfo | None
    username: str

    def __init__(self, url: str, username: str='', password: str='',
                 token: str = '',
                 session: HttpSession | None = None) -> None:
        self.base_url = url
        self.username = username
        self.password = password
        self.token = token
        if session:
            self.session = session
        else:
            self.session = cast(HttpSession, requests.Session())
        self.csrf_tokens = {}
        self.keys = {}
        self.streams = {}
        self.log = logging.getLogger('management')
        self.user = None

    def login(self) -> bool:
        if self.user:
            return True
        login_url: str = self.url_for('api-login')
        fields: LoginRequestJson = {
            "username": self.username,
            "password": self.password,
            "rememberme": False,
        }
        if self.token:
            fields['token'] = self.token
        result: HttpResponse = self.session.post(login_url, json=cast(JsonObject, fields))
        if result.status_code != 200:
            self.log.warning('Login HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            return False
        js: LoginResponseJson = cast(LoginResponseJson, result.json())
        if js.get('error'):
            self.log.error('%s', js.get('error'))
            return False
        try:
            user: UserSummaryJson = js['user'] # pyright: ignore[reportTypedDictNotRequiredAccess]
            self.user = UserInfo(**user)
            return True
        except KeyError as err:
            self.log.error('%s', js.get('error'))
            return False

    def fetch_media_info(self, with_details: bool = False) -> bool:
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

    def get_streams(self) -> list[StreamInfo]:
        return self.streams.values()

    def get_stream_info(self, directory: str) -> StreamInfo | None:
        if directory not in self.streams:
            self.fetch_media_info()
        if directory not in self.streams:
            self.log.debug('Failed to find information for stream "%s"', directory)
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

    def get_keys(self) -> dict[str, KeyInfo]:
        return self.keys

    def add_key(self, kid: str, computed: bool,
                key: str | None = None, alg: str | None = None) -> bool:
        if kid in self.keys:
            return True
        params = {
            'kid': kid,
            'csrf_token': self.csrf_tokens['kids']
        }
        if key is not None:
            params['key'] = key
        url = self.url_for('add-key')
        self.log.debug('AddKey PUT %s', url)
        result = self.session.put(url, params=params)
        try:
            js = result.json()
        except ValueError:
            js = {}
        if 'csrf_token' in js:
            self.csrf_tokens['kids'] = js['csrf_token']
        if result.status_code != 200 or 'error' in js:
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            if 'error' in js:
                self.log.error('%s', js['error'])
            return False
        js = result.json()
        self.keys[js['kid']] = {
            'kid': js['kid'],
            'key': js['key'],
            'computed': js['computed'],
        }
        return True

    def add_stream(self, directory: str, title: str, marlin_la_url: str = '',
                   playready_la_url: str = '', **kwargs) -> StreamInfo | None:
        try:
            return self.streams[directory]
        except KeyError:
            pass
        params = {
            'title': title,
            'directory': directory,
            'marlin_la_url': marlin_la_url,
            'playready_la_url': playready_la_url,
            'csrf_token': self.csrf_tokens['streams']
        }
        url = self.url_for('add-stream')
        self.log.debug('PUT %s', url)
        result = self.session.put(url, json=params)
        if result.status_code != 200:
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            self.log.error('Add stream failure: HTTP %d', result.status_code)
            return None
        js = result.json()
        if 'csrf_token' in js:
            self.csrf_tokens['streams'] = js['csrf_token']
        if js.get('error') is not None:
            self.log.error('Add stream failure: %s', js['error'])
            return None
        ds = StreamInfo(**js)
        self.streams[js['directory']] = ds
        ds.csrf_tokens = {'streams': js['csrf_token']}
        return ds

    def upload_file(self, stream: StreamInfo, filename: Path) -> bool:
        if filename.stem in stream.media_files:
            return True
        params = {
            'ajax': 1,
            'stream': stream.pk,
            'submit': 'Submit',
            'csrf_token': self.get_stream_csrf_token(stream, 'upload'),
        }
        self.log.debug('Upload file: %s', params)
        upload_url = urllib.parse.urljoin(self.base_url, stream.upload_url)
        with filename.open('rb') as mp4_src:
            files = [
                ('file', (str(filename.name), mp4_src, 'video/mp4')),
            ]
            self.log.debug('POST %s', stream.upload_url)
            result = self.session.post(
                upload_url, data=params, files=files)
        if result.status_code != 200:
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            return False
        js = result.json()
        if 'csrf_token' in js:
            stream.csrf_tokens['upload'] = js['csrf_token']
        if 'upload_url' in js:
            stream.upload_url = js['upload_url']
        if 'error' in js:
            self.log.warning('Error: %s', js['error'])
            return False
        js['representation'] = None
        stream.media_files[filename.stem] = js
        return True

    def index_file(self, stream: StreamInfo, name: Path) -> bool:
        params = {
            'ajax': 1,
            'csrf_token': self.get_stream_csrf_token(stream, 'files'),
        }
        if name.stem not in stream.media_files:
            self.log.warning('File "%s" not found', name)
            return False
        mfid = stream.media_files[name.stem]['pk']
        url = self.url_for('index-media-file', mfid=mfid)
        timeout = 15
        while timeout > 0:
            self.log.debug('GET %s', url)
            result = self.session.get(url, params=params)
            try:
                js = result.json()
            except (ValueError) as err:
                js = {'errors': [str(err)]}
            if 'csrf_token' in js:
                stream.csrf_tokens['files'] = js['csrf_token']
                params['csrf_token'] = js['csrf_token']
            errors: list[str] | None = js.get('errors')
            if result.status_code == 200 and not errors:
                stream.media_files[name.stem]['representation'] = js['representation']
                return True
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            if errors is not None:
                for err in errors:
                    self.log.error('%s', err)
            if result.status_code != 404 or timeout == 0:
                if timeout == 0:
                    self.log.error('Timeout uploading file "%s"', name)
                else:
                    self.log.error('Error uploading file "%s"', name)
                return False
            timeout -= 1
            time.sleep(2)
        self.log.error('Timeout uploading file "%s"', name)
        return False

    def set_timing_ref(self, stream: StreamInfo, timing_ref: str) -> bool:
        url = self.url_for('view-stream', spk=stream.pk) + '?ajax=1'
        self.log.debug('GET %s', url)
        result = self.session.get(url)
        if result.status_code != 200:
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            self.log.error('Add stream failure: HTTP %d', result.status_code)
            return False
        js = result.json()
        if 'csrf_tokens' in js:
            self.csrf_tokens.update(js['csrf_tokens'])
        data = {
            'csrf_token': self.csrf_tokens['streams'],
            'timing_ref': timing_ref,
        }
        for name in {'title', 'directory', 'marlin_la_url', 'playready_la_url'}:
            data[name] = js[name]
        self.log.debug('POST %s', url)
        result = self.session.post(url, json=data)
        if result.status_code != 200:
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            self.log.error('Add stream failure: HTTP %d', result.status_code)
            return False
        js = result.json()
        if 'csrf_token' in js:
            self.csrf_tokens['streams'] = js['csrf_token']
        stream = StreamInfo(**js)
        self.streams[stream.directory] = stream
        return True

    def url_for(self, name, **kwargs) -> str:
        route = routes[name]
        path = route.formatTemplate.format(**kwargs)
        return urllib.parse.urljoin(self.base_url, path)

    def get_stream_csrf_token(self, stream: StreamInfo, service: str) -> str:
        token = stream.csrf_tokens[service]
        if token is None:
            s_info = self.get_stream_info(stream.directory)
            stream.csrf_tokens.update(s_info.csrf_tokens)
            token = stream.csrf_tokens[service]
        stream.csrf_tokens[service] = None
        return token
