from HTMLParser import HTMLParser
import json
import logging
import os
import ssl
import sys
import time
import urllib

import certifi
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

    def login(self):
        if self._has_logged_in:
            return True
        self.log.info('GET %s', self.routes.login)
        result = self.session.get(self.routes.login)
        if result.status_code != 200:
            print('HTTP status {}'.format(result.status_code))
            print(result.headers)
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
        self.log.info('GET %s', fp.form['action'])
        result = self.session.get(fp.form['action'],
                                  params=fields)
        self._has_logged_in = result.status_code == 200 and \
                              'dev_appserver_login' in self.session.cookies
        return self._has_logged_in

    def get_media_info(self):
        self.login()
        self.log.info('GET %s', self.routes.media)
        result = self.session.get(self.routes.media, params={'ajax':1})
        if result.status_code != 200:
            print('HTTP status {}'.format(result.status_code))
            print(result.headers)
            return False
        js = result.json()
        self.csrf_tokens.update(js['csrf_tokens'])
        for f in js['files']:
            self.files[f['name']] = f
        for k in js['keys']:
            kid = k['kid']
            self.keys[kid] = k
        for s in js['streams']:
            self.streams[s['prefix']] = s
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
        self.log.info('PUT %s', self.routes.media)
        result = self.session.put(self.routes.key, params=params)
        try:
            js = result.json()
        except ValueError:
            js = {}
        if 'csrf' in js:
            self.csrf_tokens['kids'] = js['csrf']
        if result.status_code != 200 or 'error' in js:
            print('HTTP status {}'.format(result.status_code))
            print(result.headers)
            if 'error' in js:
                print(js['error'])
            return False
        js = result.json()
        self.keys[js['kid']] = {
            'kid': js['kid'],
            'key': js['key'],
            'computed': js['computed'],
        }
        return True
        
    def add_stream(self, prefix, title):
        if prefix in self.streams:
            return True
        params = {
            'title': title,
            'prefix': prefix,
            'csrf_token': self.csrf_tokens['streams']
        }
        self.log.info('PUT %s', self.routes.stream)
        result = self.session.put(self.routes.stream, params=params)
        try:
            js = result.json()
        except ValueError:
            js = {}
        if 'csrf' in js:
            self.csrf_tokens['streams'] = js['csrf']
        if result.status_code != 200 or 'error' in js:
            print('HTTP status {}'.format(result.status_code))
            print(result.headers)
            if 'error' in js:
                print(js['error'])
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
        self.log.info('POST %s', self.upload_url)
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
            print('HTTP status {}'.format(result.status_code))
            print(result.headers)
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
        self.log.info('GET %s', url)
        result = self.session.get(url, params=params)
        try:
            js = result.json()
        except (ValueError) as err:
            js = { 'error': str(err) }
        if 'csrf' in js:
            self.csrf_tokens['files'] = js['csrf']
        if result.status_code != 200 or 'error' in js:
            print('HTTP status {}'.format(result.status_code))
            print(result.headers)
            if 'error' in js:
                print(js['error'])
            return False
        self.files[name]['representation'] = js['representation']
        return True
        
        
if __name__ == "__main__":
    with open(sys.argv[2], 'r') as js:
        config = json.load(js)
    mm = MediaManagement(sys.argv[1])
    mm.login()
    mm.get_media_info()
    for k in config['keys']:
        if k['kid'] not in mm.keys:
            print('Add key KID={kid} computed={computed}'.format(**k))
            if not mm.add_key(**k):
                print('Failed to add key {kid}'.format(**k))
    for s in config['streams']:
        if s['prefix'] not in mm.streams:
            print('Add stream prefix="{prefix}" title="{title}"'.format(**s))
            if not mm.add_stream(**s):
                print('Failed to add stream {prefix}: {title}'.format(**s))
    for name in config['files']:
        if name not in mm.files:
            filename = name
            if not os.path.exists(filename):
                d = os.path.dirname(sys.argv[2])
                filename = os.path.join(d, name)
                if not os.path.exists(filename):
                    print("{} not found".format(name))
                    continue
            print('Add file {}'.format(name))
            if not mm.upload_file(name, filename):
                print('Failed to add file {}'.format(name))
                continue
            time.sleep(2) # allow time for DB to sync
        if mm.files[name]['representation'] is None:
            print('Index file {}'.format(name))
            timeout = 3
            done = False
            while timeout > 0 and not done:
                done = mm.index_file(name)
                if not done:
                    timeout -= 1
                    time.sleep(1.5)
            if not done:
                print('Failed to index file {}'.format(name))
                

