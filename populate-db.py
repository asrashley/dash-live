from __future__ import print_function
import argparse
import json
import logging
from pathlib import Path
import os
import ssl
import sys
import time
import urllib

import requests

from dashlive.server.routes import routes

class MediaManagement:
    def __init__(self, url: str, username: str, password: str) -> None:
        self.base_url = url
        self.username = username
        self.password = password
        self.session = requests.Session()
        self._has_logged_in = False
        self.files = {}
        self.csrf_tokens = {}
        self.upload_url = None
        self.keys = {}
        self.streams = {}
        self.log = logging.getLogger('MediaManagement')

    def url_for(self, name, **kwargs) -> str:
        route = routes[name]
        # print('formatTemplate', route.formatTemplate)
        path = route.formatTemplate.format(**kwargs)
        # print('path', path)
        return urllib.parse.urljoin(self.base_url, path)

    def populate_database(self, jsonfile):
        with open(jsonfile, 'r') as js:
            config = json.load(js)
        self.login()
        self.get_media_info()
        for k in config['keys']:
            if k['kid'] not in self.keys:
                self.log.info('Add key KID={kid} computed={computed}'.format(**k))
                if not self.add_key(**k):
                    self.log.error('Failed to add key {kid}'.format(**k))
        directory = None
        for s in config['streams']:
            directory = s.get('directory')
            if 'prefix' in s:
                directory = s['prefix']
                s['directory'] = directory
                del s['prefix']
            if directory not in self.streams:
                self.log.info(f'Add stream directory="{directory}" title="{s["title"]}"')
                if not self.add_stream(**s):
                    self.log.error(f'Failed to add stream {directory}: {s["title"]}')
            directory = s['directory']
        if directory is None and config['files']:
            prefix = name.split('_')[0]
            if prefix not in self.streams:
                s = {
                    'title': name,
                    'directory': prefix
                }
                if not self.add_stream(**s):
                    self.log.error(f'Failed to add stream {s.directory}: {s.title}')
                    return False
                directory = prefix
        self.get_media_info()
        for name in config['files']:
            name = Path(name)
            if name.stem not in self.files:
                filename = name
                if not os.path.exists(filename):
                    # d = os.path.dirname(jsonfile)
                    js_dir = Path(jsonfile).parent
                    filename = js_dir / filename
                    if not filename.exists():
                        self.log.warning("%s not found", name)
                        continue
                self.log.info('Add file %s', filename.name)
                try:
                    stream = self.streams[directory]
                except KeyError:
                    self.log.error(f'Unknown stream "{directory}"')
                    continue
                if not self.upload_file(stream['pk'], filename):
                    self.log.error('Failed to add file %s', name)
                    continue
                time.sleep(2) # allow time for DB to sync
            if self.files[name.stem]['representation'] is None:
                self.log.info('Index file %s', name)
                if not self.index_file(name):
                    self.log.error('Failed to index file %s', name)

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

    def get_media_info(self):
        self.login()
        url = self.url_for('media-list')
        self.log.debug('GET %s', url)
        result = self.session.get(url, params={'ajax': 1})
        if result.status_code != 200:
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            return False
        js = result.json()
        self.csrf_tokens.update(js['csrf_tokens'])
        self.files = {}
        self.upload_url = None
        self.keys = {}
        self.streams = {}
        for f in js['files']:
            self.files[f['name']] = f
            self.log.debug('File %s', f['name'])
        for k in js['keys']:
            kid = k['kid']
            self.log.debug('KID %s: computed=%s', kid, k['computed'])
            self.keys[kid] = k
        for s in js['streams']:
            self.streams[s['directory']] = s
            self.log.debug('Stream %s: %s', s['directory'], s['title'])
        self.upload_url = urllib.parse.urljoin(self.base_url, js['upload_url'])
        return True

    def add_key(self, kid, computed, key=None):
        if kid in self.keys:
            return True
        params = {
            'kid': kid,
            'csrf_token': self.csrf_tokens['kids']
        }
        if key is not None:
            params['key'] = key
        url = self.url_for('key')
        self.log.debug('AddKey PUT %s', url)
        result = self.session.put(url, params=params)
        try:
            js = result.json()
        except ValueError:
            js = {}
        if 'csrf' in js:
            self.csrf_tokens['kids'] = js['csrf']
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

    def add_stream(self, directory, title, marlin_la_url='', playready_la_url=''):
        if directory in self.streams:
            return True
        params = {
            'title': title,
            'directory': directory,
            'marlin_la_url': marlin_la_url,
            'playready_la_url': playready_la_url,
            'csrf_token': self.csrf_tokens['streams']
        }
        url = self.url_for('stream')
        self.log.debug('PUT %s', url)
        result = self.session.put(url, json=params)
        if result.status_code != 200:
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            return False
        js = result.json()
        if 'csrf' in js:
            self.csrf_tokens['streams'] = js['csrf']
        if 'error' in js:
            self.log.error(js['error'])
            return False
        self.streams[js['directory']] = {
            'title': js['title'],
            'directory': js['directory'],
            'pk': js['pk'],
            'blob': js['blob'],
        }
        return True

    def upload_file(self, stream_pk: int, filename: Path) -> bool:
        if filename.stem in self.files:
            return True
        params = {
            'ajax': 1,
            'stream': stream_pk,
            'submit': 'Submit',
            'csrf_token': self.csrf_tokens['upload']
        }
        self.log.debug('Upload file: %s', params)
        files = [
            ('file', (str(filename.name), filename.open('rb'), 'video/mp4')),
        ]
        self.log.debug('POST %s', self.upload_url)
        result = self.session.post(self.upload_url, data=params, files=files)
        if result.status_code != 200:
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            return False
        js = result.json()
        if 'csrf' in js:
            self.csrf_tokens['upload'] = js['csrf']
        if 'upload_url' in js:
            self.upload_url = urllib.parse.urljoin(self.base_url, js['upload_url'])
        if 'error' in js:
            self.log.warning('Error: %s', js['error'])
            return False
        js['representation'] = None
        self.files[filename.stem] = js
        return True

    def index_file(self, name: Path) -> bool:
        params = {
            'ajax': 1,
            'csrf_token': self.csrf_tokens['files']
        }
        if name.stem not in self.files:
            print('File {} not found'.format(name))
            return False
        mfid = self.files[name.stem]['pk']
        url = self.url_for('media-index', mfid=mfid)
        timeout = 10
        while timeout > 0:
            self.log.debug('GET %s', url)
            result = self.session.get(url, params=params)
            try:
                js = result.json()
            except (ValueError) as err:
                js = { 'error': str(err) }
            if 'csrf' in js:
                self.csrf_tokens['files'] = js['csrf']
                params['csrf_token'] = js['csrf']
            if result.status_code != 200 or 'error' in js:
                self.log.warning('HTTP status %d', result.status_code)
                self.log.debug('HTTP headers %s', str(result.headers))
                if 'error' in js:
                    self.log.error('%s', str(js['error']))
                if result.status_code == 404 and timeout > 0:
                    timeout -= 1
                    time.sleep(2)
                else:
                    return False
            else:
                self.files[name.stem]['representation'] = js['representation']
                return True
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
