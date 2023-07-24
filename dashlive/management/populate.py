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
import argparse
import json
import logging
from pathlib import Path
import time
from typing import Optional
import urllib

from dashlive.utils.json_object import JsonObject

from .base import ManagementBase
from .info import StreamInfo

class PopulateDatabase(ManagementBase):
    """
    Helper class that uses a JSON file to describe a set of
    streams, keys and files that it will upload to the server.
    """

    def populate_database(self, jsonfile: str) -> bool:
        with open(jsonfile, 'r') as js:
            config = json.load(js)
        if 'files' in config:
            config = self.convert_v1_json_data(config)
        js_dir = Path(jsonfile).parent
        if not self.login():
            print('Failed to log in to server')
            return False
        self.get_media_info()
        result = True
        for k in config['keys']:
            if k['kid'] not in self.keys:
                self.log.info('Add key KID={kid} computed={computed}'.format(**k))
                if not self.add_key(**k):
                    self.log.error('Failed to add key {kid}'.format(**k))
                    result = False
        directory = None
        for s in config['streams']:
            directory = s.get('directory')
            if directory not in self.streams:
                self.log.info(f'Add stream directory="{directory}" title="{s["title"]}"')
                if not self.add_stream(**s):
                    self.log.error(f'Failed to add stream {directory}: {s["title"]}')
                    result = False
                    continue
            s_info = self.get_stream_info(directory)
            if s_info is None:
                continue
            for name in s['files']:
                if not self.upload_file_and_index(js_dir, s_info, name):
                    result = False
        return result

    def convert_v1_json_data(self, v1json: JsonObject) -> JsonObject:
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
                prefix = filename.split('_')[0]
                if prefix not in file_prefixes:
                    v1json['streams'].append({
                        'title': prefix,
                        'prefix': prefix
                    })
                    file_prefixes.add(prefix)
            v1json['streams'].sort(key=lambda item: item['prefix'])
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
            new_st['files'].sort()
            output['streams'].append(new_st)
        return output

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
                   playready_la_url: str = '', **kwargs) -> Optional[StreamInfo]:
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

    def upload_file_and_index(self, js_dir: Path, stream: StreamInfo, name: str) -> bool:
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
        time.sleep(2)  # allow time for DB to sync
        if stream.media_files[name.stem]['representation'] is None:
            self.log.info('Index file %s', name)
            if not self.index_file(stream, name):
                self.log.error('Failed to index file %s', name)
                return False
        return True

    def get_stream_csrf_token(self, stream: StreamInfo, service: str) -> str:
        token = stream.csrf_tokens[service]
        if token is None:
            s_info = self.get_stream_info(stream.directory)
            stream.csrf_tokens.update(s_info.csrf_tokens)
            token = stream.csrf_tokens[service]
        stream.csrf_tokens[service] = None
        return token

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
                upload_url, data=params, files=files,
                content_type="multipart/form-data")
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
                js = {'error': str(err)}
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
                        default="http://localhost:5000/")
        ap.add_argument('--username')
        ap.add_argument('--password')
        ap.add_argument('jsonfile', help='JSON file', nargs='+', default=None)
        args = ap.parse_args()
        mm_log = logging.getLogger('PopulateDatabase')
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s: %(funcName)s:%(lineno)d: %(message)s'))
        mm_log.addHandler(ch)
        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
            mm_log.setLevel(logging.DEBUG)
        else:
            mm_log.setLevel(logging.INFO)
        mm = PopulateDatabase(args.host, args.username, args.password)
        for jsonfile in args.jsonfile:
            mm.populate_database(jsonfile)
