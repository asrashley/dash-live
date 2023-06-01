import argparse
from HTMLParser import HTMLParser
import json
import logging
import os
import ssl
import sys
import time
import urllib

import requests

class FormParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.form = None
        self.fields = {}

    def handle_starttag(self, tag, attrs):
        if tag=='form':
            a = {}
            for name, value in attrs:
                a[name] = value
            self.form = {
                'method': a['method'].upper(),
                'action': a['action'],
            }
        elif tag=='input':
            name = None
            a = {}
            for k, v in attrs:
                if k == 'name':
                    name = v
                else:
                    a[k] = v
            assert name is not None
            self.fields[name] = a

    def handle_endtag(self, tag):
        pass

    def handle_data(self, data):
        pass

class Routes(object):
    def __init__(self, base_url):
        self.base_url = base_url
        self.media = "{0}media".format(self.base_url)
        self.login = "{0}_ah/login?continue={1}".format(self.base_url,
                                                        urllib.quote(self.base_url))
        self.key = "{}key".format(self.base_url)
        self.stream = "{}stream".format(self.base_url)

    def media_info(self, mfid):
        return "{base_url}media/{mfid}".format(base_url=self.base_url, mfid=mfid)

class MediaManagement(object):
    def __init__(self, url):
        self.routes = Routes(url)
        self.session = requests.Session()
        self._has_logged_in = False
        self.files = {}
        self.csrf_tokens = {}
        self.upload_url = None
        self.keys = {}
        self.streams = {}
        self.log = logging.getLogger('MediaManagement')

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
        for s in config['streams']:
            if s['prefix'] not in self.streams:
                self.log.info('Add stream prefix="{prefix}" title="{title}"'.format(**s))
                if not self.add_stream(**s):
                    self.log.error('Failed to add stream {prefix}: {title}'.format(**s))
        for name in config['files']:
            if name not in self.files:
                filename = name
                if not os.path.exists(filename):
                    d = os.path.dirname(jsonfile)
                    filename = os.path.join(d, name)
                    if not os.path.exists(filename):
                        self.log.warning("%s not found", name)
                        continue
                self.log.info('Add file %s', name)
                if not self.upload_file(name, filename):
                    self.log.error('Failed to add file %s', name)
                    continue
                time.sleep(2) # allow time for DB to sync
            if self.files[name]['representation'] is None:
                self.log.info('Index file %s', name)
                if not self.index_file(name):
                    self.log.error('Failed to index file %s', name)

    def login(self):
        if self._has_logged_in:
            return True
        self.log.debug('GET %s', self.routes.login)
        result = self.session.get(self.routes.login)
        if result.status_code != 200:
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            return False
        fp = FormParser()
        fp.feed(result.text)
        fields = {
            "email": fp.fields['email']['value'],
            "admin": True,
            "action": "Login",
            "continue": self.routes.base_url,
        }
        assert fp.form['method'] == 'GET'
        self.log.debug('GET %s', fp.form['action'])
        result = self.session.get(fp.form['action'],
                                  params=fields)
        self._has_logged_in = result.status_code == 200 and \
                              'dev_appserver_login' in self.session.cookies
        return self._has_logged_in

    def get_media_info(self):
        self.login()
        self.log.debug('GET %s', self.routes.media)
        result = self.session.get(self.routes.media, params={'ajax':1})
        if result.status_code != 200:
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            return False
        js = result.json()
        self.csrf_tokens.update(js['csrf_tokens'])
        for f in js['files']:
            self.files[f['name']] = f
            self.log.debug('File %s', f['name'])
        for k in js['keys']:
            kid = k['kid']
            self.log.debug('KID %s: computed=%s', kid, k['computed'])
            self.keys[kid] = k
        for s in js['streams']:
            self.streams[s['prefix']] = s
            self.log.debug('Stream %s: %s', s['prefix'], s['title'])
        self.upload_url = js['upload_url']
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
        self.log.debug('PUT %s', self.routes.media)
        result = self.session.put(self.routes.key, params=params)
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

    def add_stream(self, prefix, title, marlin_la_url='', playready_la_url=''):
        if prefix in self.streams:
            return True
        params = {
            'title': title,
            'prefix': prefix,
            'marlin_la_url': marlin_la_url,
            'playready_la_url': playready_la_url,
            'csrf_token': self.csrf_tokens['streams']
        }
        self.log.debug('PUT %s', self.routes.stream)
        result = self.session.put(self.routes.stream, params=params)
        try:
            js = result.json()
        except ValueError:
            js = {}
        if 'csrf' in js:
            self.csrf_tokens['streams'] = js['csrf']
        if result.status_code != 200 or 'error' in js:
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            if 'error' in js:
                self.log.error(js['error'])
            return False
        self.streams[js['prefix']] = {
            'title': js['title'],
            'prefix': js['prefix'],
            'id': js['id'],
        }
        return True

    def upload_file(self, name, filename):
        if name in self.files:
            return True
        params = {
            'ajax': 1,
            'submit': 'Submit',
            'csrf_token': self.csrf_tokens['upload']
        }
        files = [
            ('file', (name, open(filename, 'rb'), 'video/mp4')),
        ]
        self.log.debug('POST %s', self.upload_url)
        result = self.session.post(self.upload_url, params=params, files=files)
        try:
            js = result.json()
        except ValueError:
            js = {}
        if 'csrf' in js:
            self.csrf_tokens['upload'] = js['csrf']
        if 'upload_url' in js:
            self.upload_url = js['upload_url']
        if result.status_code != 200 or 'error' in js:
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            return False
        self.files[name] = {
            'blob': js['blob'],
            'key': js['key'],
            'filename': name,
            'representation': None,
        }
        return True

    def index_file(self, name):
        params = {
            'ajax': 1,
            'index': 1,
            'csrf_token': self.csrf_tokens['files']
        }
        if name not in self.files:
            print('File {} not found'.format(name))
            return False
        mfid = self.files[name]['key']
        url = self.routes.media_info(mfid)
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
                self.files[name]['representation'] = js['representation']
                return True
        return False


    @classmethod
    def main(cls):
        ap = argparse.ArgumentParser(description='dashlive database population')
        ap.add_argument('--debug', action="store_true")
        ap.add_argument('--host', help='HTTP address of host to populate',
                        default="http://localhost:9080/" )
        ap.add_argument('jsonfile', help='JSON file', nargs='+', default=None)
        args = ap.parse_args()
        mm_log = logging.getLogger('MediaManagement')
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s: %(message)s'))
        mm_log.addHandler(ch)
        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
            mm_log.setLevel(logging.DEBUG)
        else:
            mm_log.setLevel(logging.INFO)
        mm = MediaManagement(args.host)
        for jsonfile in args.jsonfile:
            mm.populate_database(jsonfile)


if __name__ == "__main__":
    MediaManagement.main()
