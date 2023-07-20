from __future__ import print_function
import argparse
import json
import logging
from pathlib import Path
import os
import ssl
import sys
import time
from typing import Dict, List, Optional
import urllib

import requests

from dashlive.server.routes import routes
from dashlive.utils.json_object import JsonObject

class DashStream:
    def __init__(self, pk: int, title: str, directory: str,
                 blob: Optional[JsonObject] = None,
                 marlin_la_url: Optional[str] = None,
                 playready_la_url: Optional[str] = None,
                 media_files: Optional[List[JsonObject]] = None,
                 keys: Optional[List[JsonObject]] = None,
                 upload_url: Optional[str] = None,
                 csrf_tokens: Optional[JsonObject] = None) -> None:
        self.pk = pk
        self.title = title
        self.directory = directory
        self.blob = blob
        self.marlin_la_url = marlin_la_url
        self.playready_la_url = playready_la_url
        self.upload_url = upload_url
        self.csrf_tokens = csrf_tokens
        self.media_files = {}
        if media_files is not None:
            for mf in media_files:
                if isinstance(mf, dict):
                    self.media_files[mf['name']] = mf


class MediaManagement:
    def __init__(self, url: str, username: str, password: str) -> None:
        self.base_url = url
        self.username = username
        self.password = password
        self.session = requests.Session()
        self._has_logged_in = False
        self.csrf_tokens = {}
        self.keys = {}
        self.streams: Dict[str, DashStream] = {}
        self.log = logging.getLogger('MediaManagement')

    def url_for(self, name, **kwargs) -> str:
        route = routes[name]
        # print('formatTemplate', route.formatTemplate)
        path = route.formatTemplate.format(**kwargs)
        # print('path', path)
        return urllib.parse.urljoin(self.base_url, path)

    def populate_database(self, jsonfile: str) -> None:
        with open(jsonfile, 'r') as js:
            config = json.load(js)
        if 'files' in config:
            config = self.convert_v1_json_data(config)
        js_dir = Path(jsonfile).parent
        if not self.login():
            print('Failed to log in to server')
            return
        self.get_media_info()
        for k in config['keys']:
            if k['kid'] not in self.keys:
                self.log.info('Add key KID={kid} computed={computed}'.format(**k))
                if not self.add_key(**k):
                    self.log.error('Failed to add key {kid}'.format(**k))
        directory = None
        for s in config['streams']:
            directory = s.get('directory')
            if directory not in self.streams:
                self.log.info(f'Add stream directory="{directory}" title="{s["title"]}"')
                if not self.add_stream(**s):
                    self.log.error(f'Failed to add stream {directory}: {s["title"]}')
            s_info = self.get_stream_info(directory)
            if s_info is None:
                continue
            for name in s['files']:
                self.upload_file_and_index(js_dir, s_info, name)

    def convert_v1_json_data(self, v1json : JsonObject) -> JsonObject:
        """
        Converts v1 JSON Schema to current JSON Schema
        """
        files = set(v1json['files'])
        output = {
            'streams': [],
            'keys': v1json['keys']
        }
        if 'streams' not in v1json:
            v1json['streams'] = []
            file_prefixes = set()
            for filename in files:
                prefix = name.split('_')[0]
                if prefix not in file_prefixes:
                    v1json['streams'].append({
                        'title': filename,
                        'prefix': prefix
                    })
                    file_prefixes.add(prefix)
        for stream in v1json['streams']:
            new_st = {
                'directory': stream['prefix'],
                'title': stream.get('title', stream['prefix']),
                'files': []
            }
            try:
                new_st["marlin_la_url"] = stream["marlin_la_url"]
            except KeyError:
                pass
            try:
                new_st["playready_la_url"] = stream["playready_la_url"]
            except KeyError:
                pass
            for filename in list(files):
                if filename.startswith(stream['prefix']):
                    new_st['files'].append(filename)
                    files.remove(filename)
            output['streams'].append(new_st)
        return output

    def login(self):
        if self._has_logged_in:
            return True
        login_url = self.url_for('login')
        self.log.debug('GET %s', login_url)
        result = self.session.get(f'{login_url}?ajax=1')
        if result.status_code != 200:
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            return False
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
            js = {'error': result.text}
        else:
            js = result.json()
        if result.status_code == 200 and not js.get('error'):
            self._has_logged_in = True
        return self._has_logged_in

    def get_media_info(self) -> bool:
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
        #for f in js['files']:
        #    self.files[f['name']] = f
        #    self.log.debug('File %s', f['name'])
        for k in js['keys']:
            kid = k['kid']
            self.log.debug('KID %s: computed=%s', kid, k['computed'])
            self.keys[kid] = k
        for s in js['streams']:
            self.streams[s['directory']] = DashStream(**s)
            self.log.debug('Stream %s: %s', s['directory'], s['title'])
        # self.upload_url = urllib.parse.urljoin(self.base_url, js['upload_url'])
        return True

    def get_stream_info(self, directory: str) -> Optional[DashStream]:
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
        return DashStream(**js)

    def add_key(self, kid: str, computed: bool,
                key: Optional[str] = None, alg: Optional[str] = None) -> bool:
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
                   playready_la_url: str = '', **kwargs) -> Optional[DashStream]:
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
        if 'csrf' in js:
            self.csrf_tokens['streams'] = js['csrf']
        if 'error' in js:
            self.log.error('Add stream failure: %s', js['error'])
            return None
        self.streams[js['directory']] = DashStream(
            title=js['title'],
            directory=js['directory'],
            pk=js['pk'],
            blob=js['blob'])
        return self.streams[js['directory']]

    def upload_file_and_index(self, js_dir: Path, stream: DashStream, name: str) -> bool:
        name = Path(name)
        if name.stem in stream.media_files:
            return True
        filename = name
        if not filename.exists():
            filename = js_dir / filename
        if not filename.exists():
            self.log.warning("%s not found", name)
            return False
        self.log.info('Add file %s', filename.name)
        if not self.upload_file(stream, filename):
            self.log.error('Failed to add file %s', name)
            return False
        time.sleep(2) # allow time for DB to sync
        if stream.media_files[name.stem]['representation'] is None:
            self.log.info('Index file %s', name)
            if not self.index_file(stream, name):
                self.log.error('Failed to index file %s', name)
                return False
        return True

    def get_stream_csrf_token(self, stream: DashStream, service: str) -> str:
        token = stream.csrf_tokens[service]
        if token is None:
            s_info = self.get_stream_info(stream.directory)
            stream.csrf_tokens.update(s_info.csrf_tokens)
            token = stream.csrf_tokens[service]
        stream.csrf_tokens[service] = None
        return token

    def upload_file(self, stream: DashStream, filename: Path) -> bool:
        if filename.stem in stream.media_files:
            return True
        params = {
            'ajax': 1,
            'stream': stream.pk,
            'submit': 'Submit',
            'csrf_token': self.get_stream_csrf_token(stream, 'upload'),
        }
        self.log.debug('Upload file: %s', params)
        files = [
            ('file', (str(filename.name), filename.open('rb'), 'video/mp4')),
        ]
        self.log.debug('POST %s', stream.upload_url)
        upload_url = urllib.parse.urljoin(self.base_url, stream.upload_url)
        result = self.session.post(upload_url, data=params, files=files)
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

    def index_file(self, stream: DashStream, name: Path) -> bool:
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
                js = { 'error': str(err) }
            if 'csrf_token' in js:
                stream.csrf_tokens['files'] = js['csrf_token']
                params['csrf_token'] = js['csrf_token']
            if result.status_code == 200 and 'error' not in js:
                stream.media_files[name.stem]['representation'] = js['representation']
                return True
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            if 'error' in js:
                self.log.error('%s', str(js['error']))
            if result.status_code != 404 or timeout == 0:
                return False
            timeout -= 1
            time.sleep(2)
        return False


    @classmethod
    def main(cls):
        ap = argparse.ArgumentParser(description='dashlive database population')
        ap.add_argument('--debug', action="store_true")
        ap.add_argument('--host', help='HTTP address of host to populate',
                        default="http://localhost:5000/" )
        ap.add_argument('--username')
        ap.add_argument('--password')
        ap.add_argument('jsonfile', help='JSON file', nargs='+', default=None)
        args = ap.parse_args()
        mm_log = logging.getLogger('MediaManagement')
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s: %(funcName)s:%(lineno)d: %(message)s'))
        mm_log.addHandler(ch)
        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
            mm_log.setLevel(logging.DEBUG)
        else:
            mm_log.setLevel(logging.INFO)
        mm = MediaManagement(args.host, args.username, args.password)
        for jsonfile in args.jsonfile:
            mm.populate_database(jsonfile)


if __name__ == "__main__":
    MediaManagement.main()
